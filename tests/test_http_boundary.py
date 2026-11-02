"""Regresiones del parser real: urlopen simulado devuelve bytes, no JSON decodificado."""
from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from cag.core import Assistant, Principal, Knowledge
from cag.openai_provider import OpenAIProvider, InvalidResponseError, ProviderResponseError


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, OPENAI_API_KEY='test-only', LLM_MODEL='test-model')
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = Assistant(OpenAIProvider())
        self.principal = Principal('A', 'ana', ('support',))
        self.knowledge = Knowledge('A', 'v1', 'Horario: 9 a 18')

    def answer(self):
        return self.app.answer(self.principal, 'horario', self.knowledge)

    def test_invalid_http_json_and_encoding_are_sanitized_and_not_cached(self):
        for body in (b'<html>private upstream data</html>', b'\xff\xff\xff'):
            with self.subTest(body=body):
                with patch('cag.openai_provider.urlopen', side_effect=lambda *a, **kw: BytesIO(body)) as opened:
                    for _ in range(2):
                        with self.assertRaises(InvalidResponseError) as caught:
                            self.answer()
                        exc = caught.exception
                        self.assertIs(type(exc), InvalidResponseError)
                        self.assertIsInstance(exc, ProviderResponseError)
                        self.assertIsInstance(exc, RuntimeError)
                        self.assertNotIn('private', str(exc))
                        self.assertTrue(exc.__suppress_context__)
                    self.assertEqual(opened.call_count, 2)
                self.assertEqual(self.app.cache, {})

    def test_valid_http_envelope_passes_parser_and_caches(self):
        body = json.dumps({'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'text': '9 a 18', 'source': 'v1', 'abstained': False})}]}]}).encode()
        with patch('cag.openai_provider.urlopen', return_value=BytesIO(body)) as opened:
            self.assertFalse(self.answer()[1])
            self.assertTrue(self.answer()[1])
            self.assertEqual(opened.call_count, 1)

    def test_network_errors_remain_distinct_and_sanitized(self):
        for failure in (HTTPError('https://example.invalid', 503, 'private', {}, None),
                        URLError('private'), TimeoutError('private')):
            with self.subTest(error=type(failure).__name__):
                with patch('cag.openai_provider.urlopen', side_effect=failure):
                    with self.assertRaises(RuntimeError) as caught:
                        self.answer()
                    self.assertNotIsInstance(caught.exception, ProviderResponseError)
                    self.assertNotIn('private', str(caught.exception))
                self.assertEqual(self.app.cache, {})
