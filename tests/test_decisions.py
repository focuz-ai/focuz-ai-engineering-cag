import unittest
from decimal import localcontext, ROUND_DOWN
from math import nextafter
from cag.decisions import decide


class DecisionTests(unittest.TestCase):
    def test_candidate_and_ambiguity(self):
        self.assertEqual(decide({'answer': .9, 'retrieve': .05, 'human': .05}, ('answer',))['decision'], 'answer')
        result = decide({'answer': .45, 'retrieve': .4, 'human': .15}, ('answer',))
        self.assertEqual((result['decision'], result['reason'], result['abstained']), ('human', 'ambiguous', True))

    def test_probability_does_not_authorize(self):
        result = decide({'answer': 1, 'retrieve': 0, 'human': 0}, ('retrieve',))
        self.assertEqual((result['decision'], result['reason']), ('human', 'unauthorized'))

    def test_ties_abstain_even_with_zero_threshold(self):
        result = decide({'answer': .5, 'retrieve': .5, 'human': 0}, ('answer', 'retrieve'), 0, 0)
        self.assertTrue(result['abstained'])

    def test_decimal_margin_boundary_is_inclusive_without_epsilon(self):
        distribution = {'answer': .6, 'retrieve': .4, 'human': 0}
        accepted = decide(distribution, ('answer',), threshold=.6, min_margin=.2)
        self.assertFalse(accepted['abstained'])
        self.assertEqual(accepted['margin'], .2)
        self.assertTrue(decide(distribution, ('answer',), threshold=.6,
                               min_margin=nextafter(.2, 1.0))['abstained'])
        self.assertTrue(decide(distribution, ('answer',), threshold=nextafter(.6, 1.0),
                               min_margin=.2)['abstained'])

    def test_margin_does_not_depend_on_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_DOWN
            for signal in context.traps:
                context.traps[signal] = True
            context.clear_flags()
            result = decide({'answer': .6, 'retrieve': .4, 'human': 0}, ('answer',), .6, .2)
            self.assertFalse(result['abstained'])
            self.assertEqual(context.prec, 2)
            self.assertEqual(context.rounding, ROUND_DOWN)
            self.assertFalse(any(context.flags.values()))

    def test_invalid_distributions_and_policy(self):
        for probabilities in ({'answer': 1}, {'answer': .9, 'retrieve': .05, 'human': .1},
                              {'answer': float('nan'), 'retrieve': 0, 'human': 0},
                              {'answer': float('inf'), 'retrieve': 0, 'human': 0},
                              {'answer': True, 'retrieve': 0, 'human': 0},
                              {'answer': 1.1, 'retrieve': -.1, 'human': 0}):
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                decide(probabilities, ('answer',))
        with self.assertRaises(ValueError):
            decide({'answer': 1, 'retrieve': 0, 'human': 0}, ('shell',))
        with self.assertRaises(ValueError):
            decide({'answer': 1, 'retrieve': 0, 'human': 0}, ({'role': 'admin'},))
        with self.assertRaises(ValueError):
            decide({'answer': 1, 'retrieve': 0, 'human': 0}, ('answer',), float('nan'))
