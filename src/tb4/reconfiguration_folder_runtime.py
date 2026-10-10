"""Trusted native Folder controller/admission composition, never activation."""
from .commissioning_state import storage_spec, validated
from .configuration_contract import require
from .desktop.reconfiguration import CandidateController
from .drive.folder_prerequisites import native_folder_prerequisites
from .drive.leadership import Leadership
from .private_settings import PrivateSettings
from .reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from .reconfiguration_candidate import Candidate
from .timing_contract import TimingProfile


def native_folder_candidate_controller(candidate, *, access, environment, clock):
    require(type(candidate) is Candidate, "CONFIGURATION_CANDIDATE_CONTEXT")
    def fresh():
        ctx = candidate.context.maintenance.context
        return native_folder_prerequisites(candidate.context.profile, access=access,
            environment=environment, source=ctx.source, runtime=ctx.runtime,
            clock=clock, normal_authority=True)
    return CandidateController(candidate, fresh)


def native_folder_admission(profile, checkpoint, *, access, environment, credential_clock,
                            clock, capabilities, source, runtime, enrollment):
    require(type(profile) is PrivateSettings, "ADMISSION_CONTEXT")
    snapshot = profile.read()
    require(snapshot is not None, "ADMISSION_PROFILE")
    payload = validated(snapshot.payload)
    require(payload["choices"]["role"] == "watchdog", "ADMISSION_PROFILE")
    checker = native_folder_prerequisites(profile, access=access, environment=environment,
        source=source, runtime=runtime, clock=credential_clock, normal_authority=True)
    _, handle = storage_spec(payload["choices"]["storage"])
    leader = Leadership(checker.storage.port.authority(handle), actor=payload["installation_id"],
        enrollment=enrollment, profile=TimingProfile.parse(payload["choices"]["timing"]))
    return ConfigurationAdmission(AdmissionContext(profile, checkpoint, leader, checker,
        capabilities, clock))
