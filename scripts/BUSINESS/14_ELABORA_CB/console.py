from colorama import Fore, Style, init


init(autoreset=True)


def titolo(testo: str) -> None:
    linea = "─" * 64
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{linea}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {testo.upper()}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{linea}")


def info(testo: str) -> None:
    print(f"{Fore.CYAN}ℹ {Style.RESET_ALL}{testo}")


def successo(testo: str) -> None:
    print(f"{Fore.GREEN}✓ {Style.RESET_ALL}{testo}")


def avviso(testo: str) -> None:
    print(f"{Fore.YELLOW}! {Style.RESET_ALL}{testo}")


def errore(testo: str) -> None:
    print(f"{Fore.RED}✕ {Style.RESET_ALL}{testo}")


def dettaglio(testo: str) -> None:
    print(f"{Fore.LIGHTBLACK_EX}  • {testo}")


def percorso(etichetta: str, valore) -> None:
    print(
        f"{Fore.MAGENTA}→ {Style.RESET_ALL}"
        f"{Style.BRIGHT}{etichetta}:{Style.RESET_ALL} {valore}"
    )


def progresso(testo: str) -> None:
    print(f"{Fore.CYAN}⟳ {testo}", end="\r", flush=True)
