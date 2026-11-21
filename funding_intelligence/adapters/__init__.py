from .bndes import BndesAdapter
from .cnpq import CnpqAdapter
from .dou import DouAdapter
from .embrapii import EmbrapiiAdapter
from .eu_horizon import EuHorizonAdapter
from .fapemig import FapemigAdapter
from .fapesq import FapesqAdapter
from .finep import FinepAdapter
from .fontes_genericas import ADAPTADORES as GENERICOS
from .pdil import PdilAdapter
from .pncp_cpsi import PncpCpsiAdapter
from .ppsus import PpsusAdapter
from .querido_diario import QueridoDiarioAdapter
from .transferegov import TransferegovAdapter
from .transferegov_apis import EspeciaisAdapter, FundoAFundoAdapter, ParceriasAdapter

ADAPTERS = {
    "bndes": BndesAdapter,
    "cnpq": CnpqAdapter,
    "embrapii": EmbrapiiAdapter,
    "fapemig": FapemigAdapter,
    "fapesq": FapesqAdapter,
    "finep": FinepAdapter,
    "pdil": PdilAdapter,
    "pncp-cpsi": PncpCpsiAdapter,
    "dou-chamadas": DouAdapter,
    "eu-horizon": EuHorizonAdapter,
    "querido-diario": QueridoDiarioAdapter,
    "ppsus": PpsusAdapter,
    "transferegov": TransferegovAdapter,
    "transferegov-especiais": EspeciaisAdapter,
    "transferegov-fundoafundo": FundoAFundoAdapter,
    "transferegov-parcerias": ParceriasAdapter,
    **GENERICOS,
}

__all__ = ["ADAPTERS"]
