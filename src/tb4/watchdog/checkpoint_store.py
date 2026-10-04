"""Protected native checkpoint CAS; pending promotion never repeats a send."""
from dataclasses import asdict, replace
import json

from tb4.configuration_contract import ConfigurationError, require
from tb4.drive.authority_transaction import OwnerGuard, RecordMutation
from tb4.drive.commissioning import frozen_plan, restored_plan
from tb4.drive.leadership import ElectionMutation, Grant, identity, transition_id
from tb4.exchange_layout import MAX_GENERATION, encoded, validate_document, Capacity, empty_document
from tb4.private_settings import PrivateSettings
from .leadership_runtime import Action, Checkpoint, Receipt

SCHEMA = "protocol/native-checkpoint-v1.schema.json"
SCHEMA_SHA256 = "4f898bd51242cd61cca59dd7a016d467898671f266d2d1f1a9e38fd79eeeb6d4"


def validated_state(value, installation_id, binding):
    require(type(value) is Checkpoint and type(value.receipts) is tuple
            and len(value.receipts) <= len(Action)
            and (value.maintenance is None or transition_id(value.maintenance)), "NATIVE_CHECKPOINT")
    if value.grant is not None:
        g = value.grant
        require(type(g) is Grant and g.owner == installation_id and type(g.epoch) is int
                and 1 <= g.epoch <= MAX_GENERATION and transition_id(g.acquisition_id), "NATIVE_CHECKPOINT")
    for name, kind in (("election", ElectionMutation), ("mutation", RecordMutation)):
        plan = getattr(value, name)
        if plan is None:
            continue
        require(type(plan) is kind and plan.binding == binding
                and plan.owner.owner == installation_id and type(plan.owner.epoch) is int
                and 1 <= plan.owner.epoch <= MAX_GENERATION, "NATIVE_CHECKPOINT")
        parts = {k:json.loads(getattr(plan,k)) for k in ("header", "protected", "before", "after")}
        require(all(encoded(v) == getattr(plan,k) for k,v in parts.items()), "NATIVE_CHECKPOINT")
        header = parts["header"]
        require(set(header) == {"layout_version", "compatibility_status", "domain_id", "layout_revision", "capacity"}
                and header["domain_id"] == binding.domain_id, "NATIVE_CHECKPOINT")
        doc = empty_document(binding.domain_id, Capacity.parse(header["capacity"]))
        doc.update(header)
        require(type(parts["before"]) is dict and parts["before"]
                and set(parts["before"]) == set(parts["after"])
                and type(parts["protected"]) is dict
                and not set(parts["protected"]) & set(parts["before"]), "NATIVE_CHECKPOINT")
        for changes in (parts["before"], parts["after"], parts["protected"]):
            require(set(changes) <= set(doc["records"]), "NATIVE_CHECKPOINT")
            probe = {**doc, "records":{**doc["records"], **changes}}
            validate_document(probe)
        if name == "election":
            require(plan.action in {"ACQUIRE", "RENEW", "REQUEST_FORCE", "EXPIRE_FORCE", "CLAIM_FORCE"}
                    and set(parts["before"]) == {"global.leadership", "global.force_request"}
                    and parts["protected"] == {}, "NATIVE_CHECKPOINT")
        else:
            require(not {"global.leadership", "global.force_request"} & set(parts["before"]), "NATIVE_CHECKPOINT")
    require(all(type(r) is Receipt and type(r.action) is Action and transition_id(r.operation_id)
                and type(r.epoch) is int and 1 <= r.epoch <= MAX_GENERATION
                and r.outcome in {"UNKNOWN", "COMPLETE", "NO_WORK", "SUPERSEDED", "NOT_DISPATCHED"}
                for r in value.receipts)
            and len({r.action for r in value.receipts}) == len(value.receipts), "NATIVE_CHECKPOINT")
    return value


class NativeCheckpoint:
    def __init__(self, store, *, installation_id, binding, create=False, owner_authorized=False, initial=None):
        require(type(store) is PrivateSettings and identity(installation_id)
                and type(create) is bool, "NATIVE_CHECKPOINT_CONTEXT")
        self.store, self.installation_id, self.binding = store, installation_id, binding
        if store.read() is None:
            require(create and owner_authorized is True, "NATIVE_CHECKPOINT_MISSING")
            state = Checkpoint() if initial is None else initial
            store.save(self._encode(state), expected_revision=0)
        else:
            require(initial is None, "NATIVE_CHECKPOINT_EXISTS")
        self.read()

    def _encode(self, state):
        validated_state(state, self.installation_id, self.binding)
        def plan(value):
            if value is None:
                return None
            return {**frozen_plan(value), **({"action":value.action} if type(value) is ElectionMutation else {})}
        result = dict(schema_version=1, kind="NATIVE_WATCHDOG_CHECKPOINT", installation_id=self.installation_id,
            authority=asdict(self.binding), checkpoint=dict(grant=None if state.grant is None else asdict(state.grant),
            election=plan(state.election), mutation=plan(state.mutation),
            receipts=[{**asdict(r), "action":r.action.value} for r in state.receipts], maintenance=state.maintenance))
        require(len(encoded(result)) <= 384 * 1024, "NATIVE_CHECKPOINT_SIZE")
        return result

    def _decode(self, value):
        try:
            require(type(value) is dict and set(value) == {"schema_version", "kind", "installation_id", "authority", "checkpoint"}
                    and type(value["schema_version"]) is int and value["schema_version"] == 1
                    and value["kind"] == "NATIVE_WATCHDOG_CHECKPOINT"
                    and value["installation_id"] == self.installation_id and value["authority"] == asdict(self.binding),
                    "NATIVE_CHECKPOINT")
            row = value["checkpoint"]
            require(type(row) is dict and set(row) == {"grant", "election", "mutation", "receipts", "maintenance"}
                    and type(row["receipts"]) is list, "NATIVE_CHECKPOINT")
            election = row["election"]
            if election is not None:
                require(type(election) is dict and "action" in election, "NATIVE_CHECKPOINT")
                raw = restored_plan({k:v for k,v in election.items() if k != "action"}, self.binding)
                election = ElectionMutation(raw.binding, raw.owner, raw.header, raw.protected, raw.before, raw.after,
                                            election["action"])
            mutation = None if row["mutation"] is None else restored_plan(row["mutation"], self.binding)
            require(all(type(r) is dict and set(r) == {"action", "operation_id", "epoch", "outcome"}
                        for r in row["receipts"]), "NATIVE_CHECKPOINT")
            state = Checkpoint(None if row["grant"] is None else Grant(**row["grant"]), election, mutation,
                tuple(Receipt(Action(r["action"]),r["operation_id"],r["epoch"],r["outcome"]) for r in row["receipts"]),
                row["maintenance"])
            require(self._encode(state) == value, "NATIVE_CHECKPOINT")
            return state
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("NATIVE_CHECKPOINT") from None

    def read(self):
        try:
            current = self.store.read()
            require(current is not None, "NATIVE_CHECKPOINT_MISSING")
            return self._decode(current.payload)
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("NATIVE_CHECKPOINT_INSPECT_REQUIRED") from None

    def replace(self, expected, desired):
        current = self.store.read()
        require(current is not None, "NATIVE_CHECKPOINT_MISSING")
        if self._decode(current.payload) != expected:
            return False
        payload = self._encode(desired)
        try:
            self.store.save(payload, expected_revision=current.revision)
        except Exception:
            # A raced revision or uncertain native promotion is never success.
            raise ConfigurationError("NATIVE_CHECKPOINT_INSPECT_REQUIRED") from None
        require(self.read() == desired, "NATIVE_CHECKPOINT_UNCONFIRMED")
        return True

    def reserve(self, transition, *, owner_authorized=False):
        require(owner_authorized is True and transition_id(transition), "CONFIGURATION_OWNER_REQUIRED")
        current = self.read()
        require(current.maintenance in {None, transition}, "CONFIGURATION_LOCAL_MAINTENANCE")
        if current.maintenance is None:
            require(self.replace(current, replace(current, maintenance=transition)), "NATIVE_CHECKPOINT_CONFLICT")
        return self.read()

    def recover_pending(self, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        try:
            with self.store.native.locked() as port:
                pending, raw = port.read("settings.pending"), port.read("settings.json")
                if pending is None:
                    return "NO_PENDING"
                candidate = self.store._decode(pending, port.binding)
                current = None if raw is None else self.store._decode(raw, port.binding)
                self._decode(candidate.payload)
                if current is not None:
                    self._decode(current.payload)
                require(candidate.revision == (0 if current is None else current.revision) + 1
                        and candidate.previous == (None if current is None else current.payload), "NATIVE_CHECKPOINT_CONFLICT")
                port.promote()
                require(port.read("settings.json") == pending, "NATIVE_CHECKPOINT_UNCONFIRMED")
            return "INSPECT_REQUIRED"
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("NATIVE_CHECKPOINT_INSPECT_REQUIRED") from None
