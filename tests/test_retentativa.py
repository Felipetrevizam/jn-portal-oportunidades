import io
import socket
import unittest
import unittest.mock
import urllib.error

from funding_intelligence.adapters import base
from funding_intelligence.adapters.finep import FinepAdapter


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RetentativaTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FinepAdapter()
        patcher = unittest.mock.patch.object(base, "ESPERAS_RETENTATIVA_S", (0.0, 0.0))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_conexao_resetada_tenta_de_novo_e_recupera(self):
        efeitos = [urllib.error.URLError(ConnectionResetError(104, "reset")), _Resposta(b"ok")]
        with unittest.mock.patch("urllib.request.urlopen", side_effect=efeitos) as urlopen:
            self.assertEqual(b"ok", self.adapter.request_bytes("https://exemplo.gov.br"))
        self.assertEqual(2, urlopen.call_count)

    def test_desiste_depois_de_tres_tentativas(self):
        with unittest.mock.patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")) as urlopen:
            with self.assertRaises(socket.timeout):
                self.adapter.request_bytes("https://exemplo.gov.br")
        self.assertEqual(3, urlopen.call_count)

    def test_404_nao_e_retentado(self):
        erro = urllib.error.HTTPError("https://exemplo.gov.br", 404, "Not Found", {}, None)
        with unittest.mock.patch("urllib.request.urlopen", side_effect=erro) as urlopen:
            with self.assertRaises(urllib.error.HTTPError):
                self.adapter.request_bytes("https://exemplo.gov.br")
        self.assertEqual(1, urlopen.call_count)

    def test_503_e_retentado(self):
        erro = urllib.error.HTTPError("https://exemplo.gov.br", 503, "Unavailable", {}, None)
        with unittest.mock.patch("urllib.request.urlopen", side_effect=[erro, _Resposta(b"ok")]):
            self.assertEqual(b"ok", self.adapter.request_bytes("https://exemplo.gov.br"))


if __name__ == "__main__":
    unittest.main()
