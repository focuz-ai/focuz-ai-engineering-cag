import json
import os
import unittest
from unittest.mock import patch
from cag.core import Assistant, Principal, Knowledge, DeterministicProvider, Answer
from cag.openai_provider import (OpenAIProvider, ProviderResponseError,
                                ProviderRefusalError, IncompleteResponseError,
                                InvalidResponseError)

class CAGTests(unittest.TestCase):
    def setUp(self):
        self.provider = DeterministicProvider()
        self.principal = Principal('A', 'ana', ('support',))
        self.doc = Knowledge('A', 'v1', 'Horario de 9 a 18')
        self.app = Assistant(self.provider)
    def test_cache_hit(self):
        self.assertFalse(self.app.answer(self.principal, 'horario', self.doc)[1])
        self.assertTrue(self.app.answer(self.principal, 'horario', self.doc)[1])
        self.assertEqual(self.provider.calls, 1)
    def test_cross_tenant_denied_even_with_cache(self):
        self.app.answer(self.principal, 'horario', self.doc)
        with self.assertRaises(PermissionError):
            self.app.answer(Principal('B','bob',('support',)), 'horario', self.doc)
    def test_role_denied(self):
        with self.assertRaises(PermissionError):
            self.app.answer(Principal('A','bob',('visitor',)), 'horario', self.doc)
    def test_user_scoped_cache(self):
        self.app.answer(self.principal, 'horario', self.doc)
        self.assertFalse(self.app.answer(Principal('A','bob',('support',)), 'horario', self.doc)[1])
    def test_content_and_prompt_invalidation(self):
        self.app.answer(self.principal, 'horario', self.doc)
        changed = Knowledge('A','v1','Horario de 10 a 19')
        self.assertFalse(self.app.answer(self.principal,'horario',changed)[1])
        self.assertFalse(self.app.answer(self.principal,'horario',changed,'v2')[1])
    def test_expiration(self):
        time = [0.0]
        app = Assistant(self.provider, ttl=1, clock=lambda:time[0])
        app.answer(self.principal,'horario',self.doc)
        time[0] = 2.0
        self.assertFalse(app.answer(self.principal,'horario',self.doc)[1])
    def test_abstention(self):
        self.assertTrue(self.app.answer(self.principal,'precio',self.doc)[0].abstained)
    def test_invalid_context(self):
        with self.assertRaises(ValueError):
            Assistant(self.provider,max_context_chars=1).answer(self.principal,'horario',self.doc)
    def test_blank_context_rejected_before_provider_and_cache(self):
        for text in ('', '   ', '\n\t ', '\u00a0', None):
            with self.subTest(text=text):
                doc = Knowledge('A', 'v1', text)
                with self.assertRaises(ValueError):
                    self.app.answer(self.principal, 'horario', doc)
                self.assertEqual(self.provider.calls, 0)
                self.assertEqual(self.app.cache, {})
    def test_blank_provider_answer_is_never_cached(self):
        for text in ('', '   ', '\n\t ', '\u00a0'):
            for abstained in (False, True):
                with self.subTest(text=text, abstained=abstained):
                    with patch.object(self.provider, 'generate', return_value=Answer(text, 'v1', abstained)) as generate:
                        for _ in range(2):
                            with self.assertRaises(ValueError):
                                self.app.answer(self.principal, 'horario', self.doc)
                        self.assertEqual(generate.call_count, 2)
                        self.assertEqual(self.app.cache, {})
    def test_bad_source_rejected(self):
        self.provider.generate = lambda *args: Answer('inventado','otro',False)
        with self.assertRaises(ValueError):
            self.app.answer(self.principal,'horario',self.doc)
    def test_optional_adapter_with_mock_transport(self):
        def transport(payload):
            self.assertFalse(payload['store'])
            self.assertEqual(payload['model'],'test-model')
            return {'status':'completed','output':[{'type':'message','content':[
                {'type':'output_text','text':'{"text":"9 a 18","source":"v1","abstained":false}'}]}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake-for-unit-test','LLM_MODEL':'test-model'}):
            provider = OpenAIProvider(transport)
            self.assertEqual(Assistant(provider).answer(self.principal,'horario',self.doc)[0].source,'v1')
    def test_optional_adapter_refusal(self):
        fixture = {'status': 'completed', 'output': [{
            'type': 'message', 'role': 'assistant', 'content': [
                {'type': 'refusal', 'refusal': 'Fictional refusal text, not for logs.'}]}]}
        self.assert_adapter_error(fixture, ProviderRefusalError)
    def test_optional_adapter_incomplete(self):
        fixture = {'status': 'incomplete',
                   'incomplete_details': {'reason': 'max_output_tokens'}, 'output': []}
        self.assert_adapter_error(fixture, IncompleteResponseError)
    def test_optional_adapter_invalid_json(self):
        self.assert_adapter_error(self.completed_text('not JSON'), InvalidResponseError)
    def test_optional_adapter_blank_output_is_never_cached(self):
        for text in ('', '   ', '\n\t ', '\u00a0'):
            with self.subTest(text=text):
                encoded = json.dumps({'text': text, 'source': 'v1', 'abstained': False})
                self.assert_adapter_error(self.completed_text(encoded), InvalidResponseError)
    def test_optional_adapter_blank_context_does_not_call_transport(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake-for-unit-test','LLM_MODEL':'test-model'}):
            transport = unittest.mock.Mock()
            provider = OpenAIProvider(transport)
            with self.assertRaises(ValueError):
                provider.generate('horario', Knowledge('A', 'v1', ' \n\t'))
            transport.assert_not_called()
    def test_optional_adapter_refusal_is_not_accepted_with_output_text(self):
        fixture = self.completed_text('{"text":"9 a 18","source":"v1","abstained":false}')
        fixture['output'][0]['content'].append({'type': 'refusal', 'refusal': 'Fictional refusal'})
        self.assert_adapter_error(fixture, ProviderRefusalError)
    def test_optional_adapter_malformed_envelopes(self):
        for fixture in (None, {'status': 'completed', 'output': None},
                        {'status': 'completed', 'output': [None]},
                        {'status': 'completed', 'output': [{'type': 'message', 'content': None}]},
                        {'status': 'completed', 'output': [{'type': 'message', 'content': [None]}]},
                        self.completed_text(None), self.completed_text('[]')):
            with self.subTest(fixture=fixture):
                self.assert_adapter_error(fixture, InvalidResponseError)
    def test_optional_adapter_failed_is_not_incomplete(self):
        self.assert_adapter_error({'status': 'failed', 'output': []}, ProviderResponseError)

    @staticmethod
    def completed_text(text):
        return {'status': 'completed', 'output': [{
            'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}

    def assert_adapter_error(self, fixture, expected_error):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake-for-unit-test','LLM_MODEL':'test-model'}):
            transport = unittest.mock.Mock(return_value=fixture)
            app = Assistant(OpenAIProvider(transport))
            for _ in range(2):
                with self.assertRaises(expected_error) as caught:
                    app.answer(self.principal, 'horario', self.doc)
                self.assertIs(type(caught.exception), expected_error)
                self.assertNotIn('Fictional', str(caught.exception))
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(app.cache, {})

if __name__ == '__main__': unittest.main()
