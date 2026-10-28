import os
import unittest
from unittest.mock import patch
from cag.core import Assistant, Principal, Knowledge, DeterministicProvider, Answer
from cag.openai_provider import OpenAIProvider

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
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake-for-unit-test','LLM_MODEL':'test-model'}):
            provider = OpenAIProvider(lambda p:{'status':'incomplete','output':[]})
            with self.assertRaises(RuntimeError):
                provider.generate('horario',self.doc)

if __name__ == '__main__': unittest.main()
