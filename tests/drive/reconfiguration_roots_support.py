"""Actual Google request construction; only a fresh synthetic provider mutates."""
import copy
from types import SimpleNamespace

from tb4.drive.commissioning_native import FOLDER, FIELDS
from tb4.reconfiguration_roots import DocsRootMoves, RootContext, SCHEMA
from reconfiguration_candidate_support import system as candidate_system, private
from test_native_docs_transport import HttpError

TARGET = "synthetic-second-root"


def system(*, root_store=None, **kwargs):
    s = candidate_system(schemas=(SCHEMA,),**kwargs)
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
    context = RootContext(s.candidate,s.checker,root_store or private(4),TARGET)
    return SimpleNamespace(candidate=s.candidate,candidate_context=s.context,checker=s.checker,
        value=s.value,context=context,roots=DocsRootMoves(context),moves=moves,before=before,
        failure=failure,media=media)
