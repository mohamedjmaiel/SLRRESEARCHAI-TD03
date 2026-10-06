"""Fixtures partagées par les tests du TD03 (ne pas modifier)."""
from types import SimpleNamespace

import pytest

from slrresearch.tools import build_registry

# Requêtes d'une RQ telles que les produit le TD02 (adaptateurs Scholar/IEEE/ACM).
QUERIES = {
    "scholar": '"large language models" OR LLM screening OR "study selection"',
    "ieee": '("All Metadata":"large language models" OR "All Metadata":LLM) '
            'AND ("All Metadata":screening)',
    "acm": 'Abstract:("large language models" OR LLM) AND Abstract:(screening)',
}


@pytest.fixture
def queries():
    return dict(QUERIES)


@pytest.fixture
def registry():
    """Fabrique de registres simulés : registry("perturbe"), registry(allowed=...)."""
    def make(scenario="stable", allowed=None):
        return build_registry("simule", scenario, allowed)
    return make


class ScriptedDecider:
    """Décideur de test : rejoue une liste d'actions, puis termine."""

    def __init__(self, actions):
        self.actions = list(actions)
        self.calls = 0

    def __call__(self, state):
        self.calls += 1
        if self.actions:
            return self.actions.pop(0)
        return {"action": "finish"}


class FakeModel:
    """ChatModel de test : rejoue des sorties texte."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.outputs.pop(0))


@pytest.fixture
def scripted():
    return ScriptedDecider


@pytest.fixture
def fake_model():
    return FakeModel
