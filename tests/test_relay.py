import io
import unittest
import unittest.mock
import urllib.error
import urllib.parse

from funding_intelligence.adapters import base
from funding_intelligence.adapters.finep import FinepAdapter


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


RELAY = "https://fomenta360.exemplo/api/coleta/relay"


def _url(pedido) -> str:
    return pedido.full_url if hasattr(pedido, "full_url") else str(pedido)


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FinepAdapter()
        patches = [
            unittest.mock.patch.object(base, "ESPERAS_RETENTATIVA_S", (0.0, 0.0)),
            unittest.mock.patch.dict("os.environ", {"FOMENTA360_RELAY_URL": RELAY, "FOMENTA360_CRON_SECRET": "segredo"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        base.HOSTS_VIA_RELAY.clear()
        self.addCleanup(base.HOSTS_VIA_RELAY.clear)

    def test_site_que_derruba_a_conexao_e_buscado_pelo_relay(self):
        efeitos = [urllib.error.URLError(ConnectionResetError(104, "reset")), _Resposta(b"pagina")]
        with unittest.mock.patch("urllib.request.urlopen", side_effect=efeitos) as urlopen:
            self.assertEqual(b"pagina", self.adapter.request_bytes("https://www.gov.br/cnpq/chamadas"))
        segundo = urlopen.call_args_list[1].args[0]
        self.assertTrue(_url(segundo).startswith(RELAY + "?url="))
        self.assertEqual("https://www.gov.br/cnpq/chamadas", urllib.parse.parse_qs(urllib.parse.urlsplit(_url(segundo)).query)["url"][0])
        self.assertEqual("Bearer segredo", segundo.get_header("Authorization"))

    def test_depois_do_primeiro_bloqueio_o_site_vai_direto_pelo_relay(self):
        efeitos = [urllib.error.URLError(ConnectionResetError(104, "reset")), _Resposta(b"a"), _Resposta(b"b")]
        with unittest.mock.patch("urllib.request.urlopen", side_effect=efeitos) as urlopen:
            self.adapter.request_bytes("https://www.gov.br/cnpq/a")
            self.assertEqual(b"b", self.adapter.request_bytes("https://www.gov.br/cnpq/b"))
        self.assertEqual(3, urlopen.call_count, "o segundo pedido não tenta direto de novo")
        self.assertTrue(_url(urlopen.call_args_list[2].args[0]).startswith(RELAY))

    def test_403_tambem_usa_o_relay(self):
        erro = urllib.error.HTTPError("https://fbb.org.br/x", 403, "Forbidden", {}, None)
        with unittest.mock.patch("urllib.request.urlopen", side_effect=[erro, _Resposta(b"ok")]):
            self.assertEqual(b"ok", self.adapter.request_bytes("https://fbb.org.br/x"))

    def test_404_nao_usa_o_relay(self):
        erro = urllib.error.HTTPError("https://www.gov.br/x", 404, "Not Found", {}, None)
        with unittest.mock.patch("urllib.request.urlopen", side_effect=erro) as urlopen:
            with self.assertRaises(urllib.error.HTTPError):
                self.adapter.request_bytes("https://www.gov.br/x")
        self.assertEqual(1, urlopen.call_count)

    def test_post_nao_passa_pelo_relay(self):
        erro = urllib.error.URLError(ConnectionResetError(104, "reset"))
        with unittest.mock.patch("urllib.request.urlopen", side_effect=[erro, _Resposta(b"ok")]) as urlopen:
            self.adapter.request_bytes("https://www.gov.br/x", method="POST", data=b"{}")
        self.assertFalse(_url(urlopen.call_args_list[1].args[0]).startswith(RELAY))

    def test_sem_relay_configurado_mantem_as_retentativas(self):
        with unittest.mock.patch.dict("os.environ", {"FOMENTA360_RELAY_URL": ""}):
            efeitos = [urllib.error.URLError(ConnectionResetError(104, "reset")), _Resposta(b"ok")]
            with unittest.mock.patch("urllib.request.urlopen", side_effect=efeitos) as urlopen:
                self.assertEqual(b"ok", self.adapter.request_bytes("https://www.gov.br/x"))
            self.assertFalse(_url(urlopen.call_args_list[1].args[0]).startswith(RELAY))


if __name__ == "__main__":
    unittest.main()
