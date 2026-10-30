import re


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def cpf_valido(cpf: str) -> bool:
    """Valida 11 dígitos e os dois dígitos verificadores."""
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * (posicao + 1 - i) for i in range(posicao))
        if (soma * 10) % 11 % 10 != int(cpf[posicao]):
            return False
    return True


def formatar_cpf(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
