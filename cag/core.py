"""CAG didáctico: contexto precargado y caché de respuestas aislado por ámbito."""
from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from time import monotonic
from typing import Protocol, Callable

@dataclass(frozen=True)
class Principal:
    tenant: str
    user: str
    roles: tuple[str, ...]

@dataclass(frozen=True)
class Knowledge:
    tenant: str
    version: str
    text: str
    allowed_roles: tuple[str, ...] = ('support',)

@dataclass(frozen=True)
class Answer:
    text: str
    source: str
    abstained: bool

class Provider(Protocol):
    model: str
    def generate(self, question: str, knowledge: Knowledge) -> Answer: ...

class DeterministicProvider:
    """Baseline extractivo. No es un LLM ni simula su calidad."""
    model = 'extractive-baseline-v1'
    def __init__(self):
        self.calls = 0
    def generate(self, question, knowledge):
        self.calls += 1
        if 'horario' not in question.lower():
            return Answer('No hay evidencia para responder.', '', True)
        return Answer(knowledge.text, knowledge.version, False)

class Assistant:
    def __init__(self, provider: Provider, ttl=60, clock: Callable = monotonic,
                 max_context_chars=12000):
        if ttl <= 0 or max_context_chars < 1:
            raise ValueError('Límites inválidos')
        self.provider, self.ttl, self.clock = provider, ttl, clock
        self.max_context_chars = max_context_chars
        self.cache = {}
        self.lock = RLock()

    def answer(self, principal: Principal, question: str, knowledge: Knowledge,
               prompt_version='v1') -> tuple[Answer, bool]:
        if principal.tenant != knowledge.tenant:
            raise PermissionError('Tenant no autorizado')
        if not set(principal.roles).intersection(knowledge.allowed_roles):
            raise PermissionError('Rol no autorizado')
        if not question.strip() or len(question) > 2000:
            raise ValueError('Consulta vacía o demasiado extensa')
        if not isinstance(knowledge.text, str) or not knowledge.text.strip():
            raise ValueError('Contexto vacío o sin texto visible')
        if len(knowledge.text) > self.max_context_chars:
            raise ValueError('Contexto excede el límite didáctico de caracteres')
        # Incluir el contenido evita reutilizar una versión declarada incorrectamente.
        scope = [principal.tenant, principal.user, sorted(principal.roles),
                 knowledge.version, knowledge.text, list(knowledge.allowed_roles),
                 prompt_version, self.provider.model, question]
        key = sha256(json.dumps(scope, ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            now = self.clock()
            self.cache = {k:v for k,v in self.cache.items() if v[0] > now}
            if key in self.cache:
                return self.cache[key][1], True
            result = self.provider.generate(question, knowledge)
            if (not isinstance(result, Answer) or not isinstance(result.text, str)
                or not result.text.strip() or not isinstance(result.source, str)
                or type(result.abstained) is not bool):
                raise ValueError('Salida del proveedor inválida')
            if not result.abstained and result.source != knowledge.version:
                raise ValueError('Fuente no corresponde al contexto')
            self.cache[key] = (self.clock() + self.ttl, result)
            return result, False
