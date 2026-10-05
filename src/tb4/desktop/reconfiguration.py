"""Trusted desktop composition of protected staged settings, never activation."""
from tb4.commissioning_state import DenyActivation
from tb4.configuration_contract import require
from tb4.reconfiguration_candidate import Candidate


class CandidateController:
    def __init__(self, candidate, checker_factory):
        require(type(candidate) is Candidate and callable(checker_factory),
                "CONFIGURATION_CANDIDATE_CONTEXT")
        self.candidate, self.checker_factory = candidate, checker_factory

    def view(self):
        return self.candidate.view()

    def choose(self, patch, *, owner_authorized=False):
        return self.candidate.choose(patch,owner_authorized=owner_authorized)

    def refresh(self):
        self.candidate._reviewed_revision = None
        return self.candidate.review(self.checker_factory())

    def activate(self):
        self.candidate._reviewed_revision = None
        checker = self.checker_factory()
        result = self.candidate.review(checker)
        if not result["settings_validated"]:
            return result
        state,_ = self.candidate._state()
        model = self.candidate._setup(state)
        result = model.activate(checker,DenyActivation())
        self.candidate._reviewed_revision = None
        return {**result, **self.view()}
