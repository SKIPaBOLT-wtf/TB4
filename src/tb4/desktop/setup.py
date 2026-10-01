"""Local setup controller. Provider/target contexts are trusted program objects.

Owner requests are persisted separately from verified storage bindings. They
cannot manufacture a domain identity, credential pin or activation grant.
"""
from dataclasses import dataclass
import ipaddress
from pathlib import Path

from tb4.commissioning_state import Setup, DenyActivation
from tb4.commissioning_checks import Environment, detect_environment, restore_setup_credentials
from tb4.private_settings import native_settings, SettingsError, require


@dataclass(frozen=True, repr=False)
class StorageSelection:
    record: dict
    verifier: object


class SetupController:
    def __init__(self, setup, *, role, environment=None, storage_selector=None,
                 checker_factory=None, credential_factory=None, credential_targets=()):
        require(type(setup) is Setup and role in {"watchdog","fetcher"}, "SETUP_CONTROLLER")
        self.setup, self.role = setup, role
        self.environment_probe = environment or (lambda:detect_environment(launch_mode="DESKTOP_SESSION"))
        self.storage_selector, self.checker_factory = storage_selector, checker_factory
        self.credential_factory, self.credential_targets = credential_factory, tuple(credential_targets)
        self.environment = None
        self.problem = None
        try:
            self.environment = self.environment_probe()
            require(type(self.environment) is Environment, "ENVIRONMENT_UNAVAILABLE")
        except Exception:
            self.problem = "ENVIRONMENT_UNAVAILABLE"
        if setup.private_choices()["role"] is None:
            setup.choose({"role":role})
        require(setup.private_choices()["role"] == role, "SETUP_ROLE_MISMATCH")
        self._storage = self._credentials = None

    def view(self):
        result = self.setup.status()
        if self.problem is not None:
            result = {**result, "state":"BLOCKED", "reason":self.problem,
                      "settings_validated":False}
        return result

    def save_owner_choices(self, *, mode, location, scope, isolated):
        require(type(isolated) is bool and type(scope) is str and type(location) is str,
                "SETUP_CHOICES_SHAPE")
        if isolated:
            require(not scope.strip(), "SETUP_SCOPE")
            networks = []
        else:
            require(scope.strip(), "SETUP_SCOPE")
            try:
                networks = [str(ipaddress.ip_network(x.strip(),strict=True)) for x in scope.split(",")]
            except ValueError:
                raise SettingsError("SETUP_SCOPE") from None
        choices = self.setup.private_choices()
        patch = {"network_scope":networks}
        bound = choices["storage"]
        if not (choices.get("storage_request") is None and bound is not None
                and mode == bound["spec"]["mode"] and location.strip() == bound["spec"]["root_id"]):
            patch["storage_request"] = dict(mode=mode,location=location.strip())
        self.setup.choose(patch)
        self._storage = self._credentials = None
        self.problem = None
        return self.view()

    def refresh(self):
        self.problem = None
        try:
            self.environment = self.environment_probe()
            require(type(self.environment) is Environment, "ENVIRONMENT_UNAVAILABLE")
            if self.setup.status()["state"] == "CANCELLED" or self.setup.missing_choices():
                return self.view()
            if "UNKNOWN" in self.setup._payload["operations"].values():
                return self.setup.review(None)
            # Saved requests/bindings are not enough: the selected current
            # authenticated adapter must resolve and verify them afresh.
            require(self.storage_selector is not None, "STORAGE_UNAVAILABLE")
            selection = self.storage_selector(self.setup.private_choices())
            require(type(selection) is StorageSelection, "STORAGE_UNAVAILABLE")
            selection.verifier.verify(selection.record)
            choices = self.setup.private_choices()
            if choices["storage"] != selection.record:
                # A changed established identity is never an automatic rebind.
                require(choices["storage"] is None, "STORAGE_UNAVAILABLE")
                self.setup.choose({"storage":selection.record})
            self._storage = selection.verifier
            if self.setup._payload.get("credential_image") is not None:
                require(self.credential_factory is not None, "CREDENTIAL_UNAVAILABLE")
                self._credentials = restore_setup_credentials(self.setup,self.credential_factory)
            elif choices["credentials"]:
                raise SettingsError("CREDENTIAL_UNAVAILABLE")
            require(self.checker_factory is not None, "INSTRUCTIONS_UNAVAILABLE")
            checker = self.checker_factory(self.environment_probe,self._storage,self._credentials)
            return self.setup.review(checker)
        except Exception as exc:
            allowed = {"ENVIRONMENT_UNAVAILABLE","STORAGE_UNAVAILABLE","CREDENTIAL_UNAVAILABLE",
                       "INSTRUCTIONS_UNAVAILABLE","SETTINGS_CHANGED_RELOAD_REQUIRED"}
            code = str(exc) if type(exc) is SettingsError else ""
            self.problem = code if code in allowed else "STORAGE_UNAVAILABLE"
            try:
                self.setup.block(self.problem if self.problem != "SETTINGS_CHANGED_RELOAD_REQUIRED"
                                 else "REVALIDATION_REQUIRED")
            except Exception:
                pass  # A missing/conflicting store cannot truthfully persist a block.
            return self.view()

    def cancel(self):
        self.problem = None
        return self.setup.cancel()

    def resume(self):
        self.problem = None
        self.setup.resume()
        return self.refresh()

    def activate(self):
        # R2 local setup does not synthesize later release/enrollment authority.
        result = self.refresh()
        if not result["settings_validated"]:
            return result
        checker = self.checker_factory(self.environment_probe,self._storage,self._credentials)
        return self.setup.activate(checker,DenyActivation())

    def select_credential(self, index, path):
        """Only owner-selected native file and an already approved target entry."""
        require(type(index) is int and 0 <= index < len(self.credential_targets)
                and isinstance(path,Path) and path.is_absolute()
                and self.credential_factory is not None, "CREDENTIAL_UNAVAILABLE")
        target = self.credential_targets[index]
        # Trusted target exposes a fixed selection helper using existing
        # RP020/021 purpose/trust rules, not JSON instructions from a widget.
        store,resolver = self.credential_factory(self.setup.installation_id)
        if self.setup._payload.get("credential_image") is not None:
            self.setup.restore_credentials(store,resolver)
        selected = target.select(store,resolver,path)
        choices = self.setup.private_choices()["credentials"]
        require(type(selected) is dict and all(x["handle"] != selected.get("handle") for x in choices),
                "SETUP_CREDENTIALS")
        self.setup.persist_credentials(store,resolver,[*choices,selected])
        self._credentials = None
        self.problem = None
        return self.view()


def open_setup(root, *, role, create=False, **adapters):
    """Explicit private path from installer/owner, not imported from public input."""
    require(isinstance(root,Path) and root.is_absolute(), "SETTINGS_PATH_INVALID")
    store = native_settings(root,create=create,owner_authorized=create)
    if not create:
        # Inspect/promote only the same complete staged next revision. Missing,
        # partial or contradictory data cannot create a replacement identity.
        store.recover_pending()
    return SetupController(Setup(store,create=create),role=role,**adapters)
