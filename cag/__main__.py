import argparse
import json
from dataclasses import asdict
from .core import Assistant, Principal, Knowledge, DeterministicProvider

parser = argparse.ArgumentParser(description='Demo Focuz CAG con datos ficticios')
parser.add_argument('--live', action='store_true', help='Llama una API real y puede generar coste')
args = parser.parse_args()
provider = DeterministicProvider()
if args.live:
    from .openai_provider import OpenAIProvider
    provider = OpenAIProvider()
app = Assistant(provider)
principal = Principal('A', 'ana', ('support',))
doc = Knowledge('A', 'policy-A-v2', 'El horario de soporte de A es lunes a viernes de 09 a 18 horas.')
for _ in range(2):
    result, hit = app.answer(principal, '¿Cuál es el horario de soporte?', doc)
    print(json.dumps({'answer': asdict(result), 'cache_hit': hit}, ensure_ascii=False))
