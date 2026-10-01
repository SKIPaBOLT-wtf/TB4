"""One explicitly selected bootstrap actor before the shared authority exists.

This is a setup grant, not a WATCHDOG lease or standby-election barrier. After
seeding, ordinary RP016 stale/forced takeover applies. Lost creation/seed replies
are inspect-only. No owner decision or live migration is inferred from access.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from .commissioning import SetupSpec, object_id, seed_document
from .docs_authority import AuthorityError, require, validated


@dataclass(frozen=True, repr=False)
class AuthorityHandle:
    object_id: str
    seal: str
    tab_id: str | None

    def __post_init__(self):
        require(object_id(self.object_id) and type(self.seal) is str and len(self.seal)==64
                and all(c in "0123456789abcdef" for c in self.seal)
                and (self.tab_id is None or object_id(self.tab_id)), "BOOTSTRAP_HANDLE")

    def record(self):
        return dict(object_id=self.object_id,seal=self.seal,tab_id=self.tab_id)

    @classmethod
    def parse(cls,value):
        require(type(value) is dict and set(value)=={"object_id","seal","tab_id"}, "BOOTSTRAP_HANDLE")
        return cls(**value)


class Bootstrap:
    def __init__(self,spec,port,journal,*,owner_authorized):
        require(type(spec) is SetupSpec and owner_authorized is True, "BOOTSTRAP_AUTHORIZATION")
        require(getattr(journal,"installation_id",None)==spec.bootstrap_actor
                and getattr(journal,"setup_id",None)==spec.setup_id, "BOOTSTRAP_ACTOR")
        require(getattr(port,"root_id",None)==spec.root_id and getattr(port,"mode",None)==spec.mode
                and getattr(port,"llm_authorized",None) is True, "BOOTSTRAP_ACCESS")
        self.spec,self.port,self.journal=spec,port,journal

    def _save(self,state):
        from tb4.exchange_layout import encoded
        self.journal.save(state)
        require(encoded(self.journal.read())==encoded(state), "BOOTSTRAP_JOURNAL_READBACK")

    def _state(self,computer_name,clock):
        require(getattr(self.journal,"locked",None) is True
                and getattr(self.journal,"protected",None) is True, "BOOTSTRAP_JOURNAL")
        state=self.journal.read()
        if state is None:
            raw=seed_document(self.spec,computer_name,clock)
            state=dict(spec=self.spec.fingerprint,phase="NOT_STARTED",handle=None,
                       seed=base64.b64encode(raw).decode("ascii"))
            self._save(state)
        require(type(state) is dict and set(state)=={"spec","phase","handle","seed"}
                and state["spec"]==self.spec.fingerprint
                and state["phase"] in {"NOT_STARTED","UNKNOWN","CREATED","SEED_UNKNOWN","COMPLETE"}
                and type(state["seed"]) is str and len(state["seed"])<=700000, "BOOTSTRAP_JOURNAL")
        try:raw=base64.b64decode(state["seed"],validate=True)
        except (ValueError,TypeError):raise AuthorityError("BOOTSTRAP_JOURNAL") from None
        validated(raw,self.spec)
        if state["handle"] is not None:AuthorityHandle.parse(state["handle"])
        require(state["handle"] is not None or state["phase"] in {"NOT_STARTED","UNKNOWN"},
                "BOOTSTRAP_JOURNAL")
        return state,raw

    def advance(self,*,computer_name,clock):
        state,raw=self._state(computer_name,clock)
        self.port.check_root()
        handle=AuthorityHandle.parse(state["handle"]) if state["handle"] is not None else None
        # Every phase verifies the same root/operation; after pinning also the
        # same exact object/tab/seal. Absence after a send never permits recreate.
        observed=self.port.inspect_authority(self.spec,handle)
        if observed is not None:
            require(type(observed) is AuthorityHandle and (handle is None or handle==observed),
                    "BOOTSTRAP_HANDLE_CHANGED")
            handle=observed
        elif state["phase"]!="NOT_STARTED":
            return "UNKNOWN"
        if state["phase"]=="NOT_STARTED":
            if handle is None:
                self._save({**state,"phase":"UNKNOWN"})
                try:handle=self.port.create_authority(self.spec)
                except Exception:return "UNKNOWN"
                if handle is None:return "UNKNOWN"
                require(type(handle) is AuthorityHandle,"BOOTSTRAP_HANDLE")
                # A provider receipt is not a confirmed existence/identity read.
                state={**state,"phase":"UNKNOWN","handle":handle.record()}
                self._save(state)
                return "INSPECT_REQUIRED"
            state={**state,"phase":"CREATED","handle":handle.record()}
            self._save(state)
            return "PROGRESS"
        if state["phase"]=="UNKNOWN":
            self._save({**state,"phase":"CREATED","handle":handle.record()})
            return "PROGRESS"
        if self.port.inspect_seed(self.spec,handle):
            self._save({**state,"phase":"COMPLETE"})
            return "AUTHORITY_READY"
        if state["phase"] in {"SEED_UNKNOWN","COMPLETE"}:
            return "UNKNOWN"
        require(state["phase"]=="CREATED","BOOTSTRAP_JOURNAL")
        self._save({**state,"phase":"SEED_UNKNOWN"})
        try:self.port.seed(self.spec,handle,raw)
        except Exception:return "UNKNOWN"
        return "INSPECT_REQUIRED"

    def initial_grant(self,leadership,clock):
        """Recover only the seeded acquisition after fresh shared verification.

        A changed acquisition requires ordinary RP016 takeover/recovery; this
        local COMPLETE marker cannot revive the original owner's lease.
        """
        from .leadership import Grant, Leadership
        require(isinstance(leadership,Leadership) and leadership.actor==self.spec.bootstrap_actor,
                "BOOTSTRAP_ACTOR")
        state,_=self._state(leadership.enrollment[leadership.actor],clock)
        require(state["phase"]=="COMPLETE","BOOTSTRAP_INCOMPLETE")
        handle=AuthorityHandle.parse(state["handle"])
        require(leadership.backend.binding==self.port.authority(handle).binding,
                "BOOTSTRAP_HANDLE_CHANGED")
        grant=Grant(self.spec.bootstrap_actor,1,self.spec.operation("authority"))
        require(leadership.current_before_dispatch(grant,clock),"OWNER_SUPERSEDED")
        return grant
