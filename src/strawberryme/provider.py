from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ExecutionEnvelope, ProviderCapabilities, RuntimeObservation, SourceIdentity
from .runtime_probe import observe_python

_STRENGTH = {"NONE": 0, "PYTHON_AUDIT": 1, "HOST_MANAGED": 2, "OS_ISOLATED": 3}


@dataclass
class LocalPythonProvider:
    provider_id: str = "local-python"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            runtime="LOCAL_SUBPROCESS",
            filesystem_enforcement="PYTHON_AUDIT",
            network_enforcement="PYTHON_AUDIT",
            process_enforcement="PYTHON_AUDIT",
            python_instrumentation=True,
            arbitrary_command=False,
        )

    def validate(self, envelope: ExecutionEnvelope, command: list[str]) -> list[str]:
        errors: list[str] = []
        required = _STRENGTH.get(envelope.required_enforcement, 99)
        caps = self.capabilities
        relevant = [caps.filesystem_enforcement]
        if envelope.network == "DENY":
            relevant.append(caps.network_enforcement)
        if envelope.process_spawn == "DENY":
            relevant.append(caps.process_enforcement)
        if any(_STRENGTH.get(value, -1) < required for value in relevant):
            errors.append(
                f"provider {self.provider_id} cannot satisfy required_enforcement={envelope.required_enforcement}"
            )
        if command:
            executable = Path(command[0]).name.lower()
            if not executable.startswith("python"):
                errors.append("local-python provider instruments Python entrypoints only")
        return errors

    def execute(
        self,
        root: Path,
        source: SourceIdentity,
        command: list[str],
        timeout_seconds: int,
        envelope: ExecutionEnvelope,
    ) -> RuntimeObservation:
        observation = observe_python(root, source, command, timeout_seconds, envelope=envelope)
        raw = observation.to_dict()
        raw["provider_id"] = self.provider_id
        raw["enforcement"] = "PYTHON_AUDIT"
        return RuntimeObservation.from_dict(raw)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers = {"local-python": LocalPythonProvider()}

    def get(self, provider_id: str):
        return self._providers.get(provider_id)

    def capabilities(self) -> list[dict[str, object]]:
        return [provider.capabilities.to_dict() for provider in self._providers.values()]
