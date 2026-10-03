"""Fresh native request fixtures for the actual adopted controller, no live host."""
import copy
from types import SimpleNamespace

from tb4.drive.commissioning_native import FOLDER,FIELDS
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_root_resume import ResumeRootContext,ResumedDocsRootMoves,SCHEMA
from tb4.reconfiguration_roots import DocsRootMoves,RootContext,SCHEMA as ROOT_SCHEMA
from reconfiguration_candidate_support import system as candidate_system,private
from reconfiguration_roots_support import TARGET
from test_native_docs_transport import HttpError
from test_reconfiguration_effects import acquire_fallback


def system(**kwargs):
    s = candidate_system(schemas=(ROOT_SCHEMA,SCHEMA),**kwargs)
    s.candidate.begin(owner_authorized=True)
    provider = s.value.provider
    provider.metadata[TARGET] = dict(id=TARGET,mimeType=FOLDER,trashed=False,capabilities=dict(canEdit=True))
    moves = []; before = [None]; failure = [None]
    media = {ref:b"synthetic retained artifact" for ref,value in provider.metadata.items()
             if value.get("mimeType") == "application/octet-stream"}
    for ref,content in media.items():
        provider.metadata[ref]["size"] = str(len(content))
    def update(**kwargs):
        assert set(kwargs) == {"fileId","body","addParents","removeParents","fields","supportsAllDrives"}
        assert kwargs["fields"] == FIELDS and kwargs["supportsAllDrives"] is True
        assert kwargs["addParents"] == TARGET and kwargs["removeParents"] == provider.spec.root_id
        assert set(kwargs["body"]) == {"properties"}
        def run():
            if before[0]:
                before[0]()
            if failure[0] == "before" or provider.metadata[TARGET]["capabilities"]["canEdit"] is not True:
                raise HttpError(403)
            value = provider.metadata[kwargs["fileId"]]
            assert value["parents"] == [provider.spec.root_id]
            value["parents"] = [TARGET]
            value["properties"] = copy.deepcopy(kwargs["body"]["properties"])
            moves.append(kwargs["fileId"])
            if failure[0] == "after":
                raise TimeoutError("SYNTHETIC_ROOT_REPLY_LOST")
            return copy.deepcopy(value)
        return provider.request("files.update",kwargs,run)
    provider.update = update
    context = RootContext(s.candidate,s.checker,private(4),TARGET)
    return SimpleNamespace(candidate=s.candidate,candidate_context=s.context,checker=s.checker,
        value=s.value,context=context,roots=DocsRootMoves(context),moves=moves,before=before,
        failure=failure,media=media)


def adopter(s, *, context=None, store=None, evidence_store=None):
    ctx = context or acquire_fallback(s.value)[2]
    evidence = ProtectedEvidence(evidence_store or private(12),installation_id=ctx.setup.installation_id,
                                 transition_id=ctx.baseline.transition_id)
    return ResumedDocsRootMoves(ResumeRootContext(ctx,store or private(11),evidence,TARGET))


def old_stores_unavailable(s):
    from tb4.private_settings import SettingsError
    def absent():
        raise SettingsError("SYNTHETIC_OLD_HOST_UNAVAILABLE")
    for store in (s.value.setup.store,s.context.store,s.value.context.store,s.value.context.baseline.store,
                  s.value.context.checkpoint.store,s.value.context.effects.store,
                  s.candidate_context.profile,s.candidate_context.archive,
                  s.candidate_context.transaction,s.candidate_context.resolution.store):
        store.read = absent
