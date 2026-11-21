from .bndes import BndesAdapter
from .cnpq import CnpqAdapter
from .embrapii import EmbrapiiAdapter
from .fapemig import FapemigAdapter
from .fapesq import FapesqAdapter
from .finep import FinepAdapter
from .fontes_genericas import ADAPTADORES as GENERICOS
from .pdil import PdilAdapter
from .ppsus import PpsusAdapter
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
    "ppsus": PpsusAdapter,
    "transferegov": TransferegovAdapter,
    "transferegov-especiais": EspeciaisAdapter,
    "transferegov-fundoafundo": FundoAFundoAdapter,
    "transferegov-parcerias": ParceriasAdapter,
    **GENERICOS,
}

__all__ = ["ADAPTERS"]
