"""Actual promoted profile, first-run and native checkpoint admission fixtures."""
from types import SimpleNamespace
from tb4.reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from reconfiguration_promotion_support import system as promotion_system


def admission_for(value, checker):
    context = AdmissionContext(value.setup.store, value.checkpoint, value.flow.leader, checker,
                               value.context.capabilities, value.context.clock)
    return context, ConfigurationAdmission(context)


def system(**kwargs):
    s = promotion_system(**kwargs)
    s.promotion.begin(s.checker, owner_authorized=True)
    assert s.promotion.advance(s.checker, owner_authorized=True) == "PROFILE_PROMOTED"
    context, admission = admission_for(s.value, s.checker)
    return SimpleNamespace(promotion=s, value=s.value, context=context, admission=admission, checker=s.checker)
