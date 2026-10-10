"""Owner-selected candidate pointer; original routing and work stay intact."""
import copy

from .commissioning_state import validated
from .drive.docs_authority import require
from .drive.folder_endpoint import NativeFolderEndpoint
from .drive.folder_endpoint_attachment import NativeFolderEndpointAttachment
from .drive.folder_endpoint_selection import selection
from .reconfiguration_candidate import Candidate


class StagedFolderEndpoint:
    def __init__(self, candidate, endpoint):
        require(type(candidate) is Candidate and type(endpoint) is NativeFolderEndpoint,
                "STAGED_FOLDER_ENDPOINT_CONTEXT")
        self.candidate, self.endpoint = candidate, endpoint
        self.link = NativeFolderEndpointAttachment(endpoint, candidate.context.profile)
        self._pins = (candidate, candidate.context, candidate.context.profile, endpoint, self.link)

    def _prepare(self, expected_selection, *, recovering=False):
        require(type(self) is StagedFolderEndpoint and type(self.candidate) is Candidate
            and type(self.endpoint) is NativeFolderEndpoint
            and type(self.link) is NativeFolderEndpointAttachment
            and (self.candidate, self.candidate.context, self.candidate.context.profile,
                 self.endpoint, self.link) == self._pins, "STAGED_FOLDER_ENDPOINT_CHANGED")
        expected = None if expected_selection is None else selection(expected_selection)
        self.candidate._reviewed_revision = None
        state, _ = self.candidate._state()
        require(state is not None and state["phase"] == "STAGED", "STAGED_FOLDER_ENDPOINT_STATE")
        self.candidate._proof(state)
        if recovering:
            # Setup.read deliberately refuses pending state. Inspect the exact
            # current native frame without promoting it or manufacturing READY.
            base = self.candidate._archive(state)
            profile = self.candidate.context.profile
            with profile.native.locked() as port:
                raw = port.read("settings.json")
                require(raw is not None, "STAGED_FOLDER_ENDPOINT_STATE")
                snapshot = profile._decode(raw, port.binding)
                self.candidate._validate_profile(snapshot.payload, base)
        else:
            snapshot = self.candidate._setup(state).snapshot
        self.link._current()
        return state, snapshot, expected

    @staticmethod
    def _desired(payload, expected, pointer):
        payload = validated(payload)
        require(pointer != expected and payload.get("folder_endpoint") == expected,
                "STAGED_FOLDER_ENDPOINT_SELECTION")
        require(payload["state"] == "INCOMPLETE" and "UNKNOWN" not in payload["operations"].values(),
                "STAGED_FOLDER_ENDPOINT_STATE")
        desired = copy.deepcopy(payload)
        desired["folder_endpoint"] = copy.deepcopy(pointer)
        return validated(desired)

    def _confirmed(self, current, expected, pointer):
        require(current.previous is not None
            and current.payload == self._desired(current.previous, expected, pointer),
                "STAGED_FOLDER_ENDPOINT_UNCONFIRMED")

    def _child(self, current, pending, port, value, pointer, expected):
        child = self.link.profile._decode(pending, port.binding)
        require(child.revision == current.revision + 1 and child.previous == current.payload
            and child.payload == self._desired(current.payload, expected, pointer),
                "STAGED_FOLDER_ENDPOINT_RECOVERY_CONFLICT")
        self.link._facts(child.payload, value, pointer)
        return child

    def _done(self, state, reference):
        self.candidate._proof(state)
        require(self.candidate._state()[0] == state, "STAGED_FOLDER_ENDPOINT_CHANGED")
        self.candidate._setup(state)
        return dict(status="SELECTED", reference=reference, metadata_only=True,
                    credential_ready=False, settings_validated=False,
                    runtime_active=False, automatic_replay=False)

    def select(self, reference, *, expected_selection, owner_authorized=False):
        require(owner_authorized is True, "STAGED_FOLDER_ENDPOINT_OWNER_REQUIRED")
        state, snapshot, expected = self._prepare(expected_selection)
        with self.link._pair(reference) as (port, current, pending, value, pointer):
            require(pending is None, "STAGED_FOLDER_ENDPOINT_PENDING")
            require(current == snapshot, "STAGED_FOLDER_ENDPOINT_CHANGED")
            if current.payload.get("folder_endpoint") == pointer:
                self._confirmed(current, expected, pointer)
            else:
                desired = self._desired(current.payload, expected, pointer)
                saved = self.link.profile._save_locked(port, desired, expected_revision=current.revision)
                require(saved.payload == desired and saved.previous == current.payload,
                        "STAGED_FOLDER_ENDPOINT_UNCONFIRMED")
                self.link._facts(saved.payload, value, pointer)
        return self._done(state, reference)

    def recover(self, reference, *, expected_selection, owner_authorized=False):
        """Promote the exact existing native child; never reconstruct or resave."""
        require(owner_authorized is True, "STAGED_FOLDER_ENDPOINT_OWNER_REQUIRED")
        state, snapshot, expected = self._prepare(expected_selection, recovering=True)
        with self.link._pair(reference) as (port, current, pending, value, pointer):
            require(current == snapshot, "STAGED_FOLDER_ENDPOINT_CHANGED")
            if pending is not None:
                self._child(current, pending, port, value, pointer, expected)
                port.promote()
                require(port.read("settings.json") == pending, "STAGED_FOLDER_ENDPOINT_UNCONFIRMED")
            else:
                self._confirmed(current, expected, pointer)
        return self._done(state, reference)
