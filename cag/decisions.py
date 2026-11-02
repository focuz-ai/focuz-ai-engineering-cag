"""Contrato de decisión con probabilidades inyectadas; no implementa Jev ni un modelo."""
import json
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from math import isclose, isfinite

CHOICES = ('answer', 'retrieve', 'human')


def decide(probabilities, allowed_actions, threshold=0.8, min_margin=0.2):
    """allowed_actions procede de política confiable, nunca de la salida del modelo."""
    if not isinstance(probabilities, dict) or set(probabilities) != set(CHOICES):
        raise ValueError('Se requieren las tres categorías exactas')
    values = list(probabilities.values())
    if any(type(x) not in (float, int) or not isfinite(x) or not 0 <= x <= 1 for x in values):
        raise ValueError('Probabilidades inválidas')
    if not isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError('Las probabilidades deben sumar 1')
    if any(type(x) not in (float, int) or not isfinite(x) or not 0 <= x <= 1
           for x in (threshold, min_margin)):
        raise ValueError('Umbral o margen inválido')
    if (not isinstance(allowed_actions, (tuple, list, set, frozenset))
            or any(not isinstance(action, str) or action not in CHOICES for action in allowed_actions)):
        raise ValueError('Política inválida')
    ordered = sorted(probabilities.items(), key=lambda item: (-item[1], item[0]))
    candidate, p_max = ordered[0]
    # Semántica decimal de la representación textual de los floats admitidos.
    # Evita que 0.6 - 0.4 quede justo debajo de una frontera inclusiva 0.2.
    # 400 cifras cubren los floats finitos [0,1], incluidos subnormales.
    with localcontext(Context(prec=400, rounding=ROUND_HALF_UP, Emin=-1000,
                              Emax=1000, capitals=1, clamp=0, flags=[], traps=[])):
        decimal_max = Decimal(str(p_max))
        decimal_margin = decimal_max - Decimal(str(ordered[1][1]))
        ambiguous = (decimal_margin <= 0 or decimal_max < Decimal(str(threshold))
                     or decimal_margin < Decimal(str(min_margin)))
    margin = float(decimal_margin)
    reason = ('ambiguous' if ambiguous
              else 'unauthorized' if candidate not in allowed_actions else 'accepted')
    return {'decision': candidate if reason == 'accepted' else 'human',
            'abstained': reason != 'accepted', 'reason': reason,
            'p_max': p_max, 'margin': margin, 'simulated_probabilities': True}


def main():
    for distribution in ({'answer': 0.9, 'retrieve': 0.05, 'human': 0.05},
                         {'answer': 0.45, 'retrieve': 0.4, 'human': 0.15}):
        print(json.dumps(decide(distribution, ('answer', 'retrieve', 'human'))))


if __name__ == '__main__':
    main()
