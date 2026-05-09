"""
card_scanner.py
===============
Scanner de cards com overlay always-on-top.

Fluxo:
  1. Captura a regiao da janela a cada ~0.3s
  2. EasyOCR detecta rank primeiro (early exit se nao for de interesse)
     depois busca nome so no bucket daquele rank
  3. Match → pressiona E + F imediatamente
  4. Envia Telegram com botoes inline:
       ✅ Confirmar coleta  →  remove (NOME, RANK) de _targets_norm + salva JSON
       ❌ Foi erro          →  mantém na lista, nada muda
  5. Regra anti-spam: mesmo (NOME, RANK) nao gera nova notificacao por 30s

Persistencia:
  - targets_removidos.json  — pares ja confirmados, nunca mais clicados
  - Carregado ao iniciar; atualizado a cada confirmacao

CONFIGURACAO:
  1. Preencha TELEGRAM_TOKEN e TELEGRAM_CHAT_ID (Opcional)
  2. Edite TARGETS_POR_RANK com os pares desejados
  3. py -3.11 card_scanner.py
"""

import json
import os
import time
import threading
import queue
import tkinter as tk
import unicodedata as _ud
import requests
import numpy as np
import cv2
import pyautogui
import mss
import easyocr
from pynput import mouse as pmouse, keyboard as pkeyboard

# ─────────────────────────────────────────────
#  CONFIGURACAO — EDITE AQUI
# ─────────────────────────────────────────────

TELEGRAM_TOKEN   = "xxxx"          # ex: "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = "xxxx"        # ex: "987654321"

# ── TARGETS POR RANK ─────────────────────────────────────────────────────────
# { "RANK": {"NOME1", "NOME2"} }  — sem acentos, MAIUSCULO
# Ranks fora do dict sao ignorados sem nem buscar o nome (early exit)
#
# Ranks disponiveis:
#   PADRAO | OURO | DIAMANTE | ARCO-IRIS
#
TARGETS_POR_RANK = {
    "PADRAO": {
        "MOUSE",
        "PIT",
        "GONK",
        "CB",
        "R3",
        "R5",
        "R8",
        "IMPERIAL PROBE",
        "B1 BATTLE",
        "DRK-1 PROBE",
        "ID10",
        "BDX EXPLORER",
        "ARG",
        "SENATE HOVERCAM",
        "BU-4D",
        "BAL-CORE",
        "ROLL-R",
        "2BB",
        "A-LT",
        "R4",
        "R9",
        "B1 SECURITY",
        "NAV-EX",
        "VECT-ARM",
        "HOV-R",
        "GROUNDMECH",
        "LO",
        "AMP WALKER",
        "SEN-TRI",
        "OPTI-POD",
        "BB",
        "R2",
        "R6",
        "TRAK-R",
        "ORB-WALKER",
        "UTIL-TEC",
        "B1 HEAVY",
        "B2 SUPER",
        "B2 HEAVY",
        "STRIKE-ORB",
        "HAUL-R",
        "LNG-SHOT",
        "PROTO-ROLLER",
        "MECHA-DROID",
        "MONO-WALKER",
        "BB9",
        "R7",
        "B2-RP",
        "CYCLO-GRAV",
        "OPTI-STRIKE"
    },
    "OURO": {
        "MOUSE",
        "PIT",
        "GONK",
        "CB",
        "R3",
        "R5",
        "R8",
        "IMPERIAL PROBE",
        "B1 BATTLE",
        "DRK-1 PROBE",
        "ID10",
        "BDX EXPLORER",
        "ARG",
        "SENATE HOVERCAM",
        "BU-4D",
        "BAL-CORE",
        "ROLL-R",
        "2BB",
        "A-LT",
        "R4",
        "R9",
        "B1 SECURITY",
        "NAV-EX",
        "VECT-ARM",
        "HOV-R",
        "GROUNDMECH",
        "LO",
        "AMP WALKER",
        "SEN-TRI",
        "OPTI-POD",
        "BB",
        "R2",
        "R6",
        "TRAK-R",
        "ORB-WALKER",
        "UTIL-TEC",
        "B1 HEAVY",
        "B2 SUPER",
        "B2 HEAVY",
        "STRIKE-ORB",
        "HAUL-R",
        "LNG-SHOT",
        "PROTO-ROLLER",
        "MECHA-DROID",
        "MONO-WALKER",
        "BB9",
        "R7",
        "B2-RP",
        "CYCLO-GRAV",
        "OPTI-STRIKE"
    },
    "DIAMANTE": {
        "MOUSE",
        "PIT",
        "GONK",
        "CB",
        "R3",
        "R5",
        "R8",
        "IMPERIAL PROBE",
        "B1 BATTLE",
        "DRK-1 PROBE",
        "ID10",
        "BDX EXPLORER",
        "ARG",
        "SENATE HOVERCAM",
        "BU-4D",
        "BAL-CORE",
        "ROLL-R",
        "2BB",
        "A-LT",
        "R4",
        "R9",
        "B1 SECURITY",
        "NAV-EX",
        "VECT-ARM",
        "HOV-R",
        "GROUNDMECH",
        "LO",
        "AMP WALKER",
        "SEN-TRI",
        "OPTI-POD",
        "BB",
        "R2",
        "R6",
        "TRAK-R",
        "ORB-WALKER",
        "UTIL-TEC",
        "B1 HEAVY",
        "B2 SUPER",
        "B2 HEAVY",
        "STRIKE-ORB",
        "HAUL-R",
        "LNG-SHOT",
        "PROTO-ROLLER",
        "MECHA-DROID",
        "MONO-WALKER",
        "BB9",
        "R7",
        "B2-RP",
        "CYCLO-GRAV",
        "OPTI-STRIKE"
    },
    "ARCO-IRIS": {
        "MOUSE",
        "PIT",
        "GONK",
        "CB",
        "R3",
        "R5",
        "R8",
        "IMPERIAL PROBE",
        "B1 BATTLE",
        "DRK-1 PROBE",
        "ID10",
        "BDX EXPLORER",
        "ARG",
        "SENATE HOVERCAM",
        "BU-4D",
        "BAL-CORE",
        "ROLL-R",
        "2BB",
        "A-LT",
        "R4",
        "R9",
        "B1 SECURITY",
        "NAV-EX",
        "VECT-ARM",
        "HOV-R",
        "GROUNDMECH",
        "LO",
        "AMP WALKER",
        "SEN-TRI",
        "OPTI-POD",
        "BB",
        "R2",
        "R6",
        "TRAK-R",
        "ORB-WALKER",
        "UTIL-TEC",
        "B1 HEAVY",
        "B2 SUPER",
        "B2 HEAVY",
        "STRIKE-ORB",
        "HAUL-R",
        "LNG-SHOT",
        "PROTO-ROLLER",
        "MECHA-DROID",
        "MONO-WALKER",
        "BB9",
        "R7",
        "B2-RP",
        "CYCLO-GRAV",
        "OPTI-STRIKE"
    }
}

# Arquivo onde ficam salvos os pares ja confirmados como coletados
ARQUIVO_REMOVIDOS = "targets_removidos.json"

# Cooldown de notificacao por par (NOME, RANK) — evita spam no Telegram
COOLDOWN_NOTIF_SEGUNDOS = 30

# Intervalo base entre capturas
INTERVALO_CAPTURA = 0.3

# Cooldown apos clicar — evita clicar 2x no mesmo card
COOLDOWN_APOS_CLIQUE = 2.5

# Delay entre E e F
DELAY_E_PARA_F = 0.1

# ─────────────────────────────────────────────
#  NORMALIZACAO
# ─────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    nfkd = _ud.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not _ud.combining(c)).upper().strip()

_RANKS_OCR = [
    "PADRAO", "OURO", "DIAMANTE", "ARCO-IRIS"
]

# ─────────────────────────────────────────────
#  FILA DE LOG (precisa existir antes de tudo)
# ─────────────────────────────────────────────

fila_log: queue.Queue = queue.Queue()

# ─────────────────────────────────────────────
#  TARGETS EM MEMORIA (mutavel em runtime)
# ─────────────────────────────────────────────

_lock_targets = threading.Lock()

_targets_norm: dict = {
    _normalizar(rank): {_normalizar(n) for n in nomes}
    for rank, nomes in TARGETS_POR_RANK.items()
}

def _carregar_removidos():
    """Remove do _targets_norm os pares ja confirmados em sessoes anteriores."""
    if not os.path.exists(ARQUIVO_REMOVIDOS):
        return
    try:
        with open(ARQUIVO_REMOVIDOS, "r", encoding="utf-8") as f:
            removidos = json.load(f)
        with _lock_targets:
            for rank, nome in removidos:
                r, n = _normalizar(rank), _normalizar(nome)
                if r in _targets_norm:
                    _targets_norm[r].discard(n)
                    if not _targets_norm[r]:
                        del _targets_norm[r]
        fila_log.put(f"[INFO] {len(removidos)} target(s) ja coletados carregados.")
    except Exception as e:
        fila_log.put(f"[ERRO] Falha ao ler JSON: {e}")

def _salvar_removido(rank: str, nome: str):
    pares = []
    if os.path.exists(ARQUIVO_REMOVIDOS):
        try:
            with open(ARQUIVO_REMOVIDOS, "r", encoding="utf-8") as f:
                pares = json.load(f)
        except Exception:
            pass
    pares.append([rank, nome])
    with open(ARQUIVO_REMOVIDOS, "w", encoding="utf-8") as f:
        json.dump(pares, f, ensure_ascii=False, indent=2)

def remover_target(rank: str, nome: str):
    r, n = _normalizar(rank), _normalizar(nome)
    with _lock_targets:
        if r in _targets_norm:
            _targets_norm[r].discard(n)
            if not _targets_norm[r]:
                del _targets_norm[r]
    _salvar_removido(r, n)
    fila_log.put(f"[LISTA] Removido: {n} / {r}")

def target_ativo(rank: str, nome: str) -> bool:
    r, n = _normalizar(rank), _normalizar(nome)
    with _lock_targets:
        return r in _targets_norm and n in _targets_norm[r]

# ─────────────────────────────────────────────
#  ESTADO GLOBAL
# ─────────────────────────────────────────────

estado = {
    "rodando":             False,
    "pausado_por_input":   False,
    "ultimo_clique":       0.0,
    "clique_script_ativo": False,
    "log_detalhado":       False,
    "usar_telegram":       True,
}

# Cooldown de notificacao por par: { (nome, rank): timestamp_ultimo_envio }
_cooldown_notif: dict  = {}
_lock_cooldown         = threading.Lock()

def _pode_notificar(nome: str, rank: str) -> bool:
    chave = (nome, rank)
    agora = time.perf_counter()
    with _lock_cooldown:
        if agora - _cooldown_notif.get(chave, 0.0) >= COOLDOWN_NOTIF_SEGUNDOS:
            _cooldown_notif[chave] = agora
            return True
    return False

# ─────────────────────────────────────────────
#  OCR
# ─────────────────────────────────────────────

print("[INIT] Carregando EasyOCR...")
reader = easyocr.Reader(["pt", "en"], gpu=True, verbose=False)
print("[INIT] EasyOCR pronto.")

# ─────────────────────────────────────────────
#  TELEGRAM — mensagem com botoes inline
# ─────────────────────────────────────────────

def _enviar_com_botoes(nome: str, rank: str):
    def _send():
        try:
            url   = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            texto = (
                f"*Card detectado!*\n"
                f"Nome: `{nome}`\n"
                f"Rank: `{rank}`\n\n"
                f"Deseja remover da lista de busca?"
            )
            teclado = {
                "inline_keyboard": [[
                    {"text": "Confirmar coleta",
                     "callback_data": f"confirmar|{rank}|{nome}"},
                    {"text": "Foi erro",
                     "callback_data": f"erro|{rank}|{nome}"},
                ]]
            }
            requests.post(url, json={
                "chat_id":      TELEGRAM_CHAT_ID,
                "text":         texto,
                "parse_mode":   "Markdown",
                "reply_markup": teclado,
            }, timeout=5)
            fila_log.put(f"[TELEGRAM] Enviado: {nome} / {rank}")
        except Exception as e:
            fila_log.put(f"[TELEGRAM] Erro: {e}")
    threading.Thread(target=_send, daemon=True).start()

def _responder_callback(callback_id: str, texto: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": texto},
            timeout=5,
        )
    except Exception:
        pass

def _editar_mensagem(chat_id, message_id: int, texto: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
            json={
                "chat_id":    chat_id,
                "message_id": message_id,
                "text":       texto,
                "parse_mode": "Markdown",
            },
            timeout=5,
        )
    except Exception:
        pass

# ─────────────────────────────────────────────
#  POLLING DE CALLBACKS DO TELEGRAM
# ─────────────────────────────────────────────

_ultimo_update_id = 0

def _loop_polling():
    global _ultimo_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    while True:
        try:
            resp = requests.get(url, params={
                "offset":          _ultimo_update_id + 1,
                "timeout":         2,
                "allowed_updates": ["callback_query"],
            }, timeout=8)
            for update in resp.json().get("result", []):
                _ultimo_update_id = update["update_id"]
                cq = update.get("callback_query")
                if cq:
                    _processar_callback(cq)
        except Exception:
            pass
        time.sleep(1)

def _processar_callback(cq: dict):
    cid        = cq["id"]
    msg        = cq.get("message", {})
    message_id = msg.get("message_id")
    chat_id    = msg.get("chat", {}).get("id")
    dados      = cq.get("data", "")

    partes = dados.split("|")
    if len(partes) != 3:
        return
    acao, rank, nome = partes

    if acao == "confirmar":
        remover_target(rank, nome)
        _responder_callback(cid, "Removido da lista!")
        _editar_mensagem(chat_id, message_id,
                         f"Coletado — removido da lista\nNome: `{nome}` | Rank: `{rank}`")
    elif acao == "erro":
        _responder_callback(cid, "Ok, mantido na lista.")
        _editar_mensagem(chat_id, message_id,
                         f"Erro de leitura — mantido na lista\nNome: `{nome}` | Rank: `{rank}`")

# ─────────────────────────────────────────────
#  ACAO: E + F + NOTIFICACAO
# ─────────────────────────────────────────────

def executar_acao(nome: str, rank: str):
    estado["clique_script_ativo"] = True
    try:
        pyautogui.press("e")
        time.sleep(DELAY_E_PARA_F)
        pyautogui.press("f")
        fila_log.put(f"[ACAO] E+F → {nome} ({rank})")
    finally:
        estado["clique_script_ativo"] = False

    estado["ultimo_clique"] = time.perf_counter()

    if estado["usar_telegram"]:
        if _pode_notificar(nome, rank):
            _enviar_com_botoes(nome, rank)
        else:
            fila_log.put(f"[TELEGRAM] Cooldown ativo — sem nova notif para {nome}/{rank}")

# ─────────────────────────────────────────────
#  OCR — dois passos com early exit
# ─────────────────────────────────────────────

def extrair_nome_rank(imagem_bgr: np.ndarray):
    resultados = reader.readtext(imagem_bgr, detail=1, paragraph=False)
    rank_detectado = "DESCONHECIDO"

    # Passo 1: rank
    for (_, texto, conf) in resultados:
        if conf < 0.3:
            continue
        texto_norm = _normalizar(texto)
        for rank_ocr in _RANKS_OCR:
            if rank_ocr in texto_norm:
                rank_detectado = rank_ocr
                break
        if rank_detectado != "DESCONHECIDO":
            break

    with _lock_targets:
        if rank_detectado not in _targets_norm:
            return None, rank_detectado
        nomes_alvo = set(_targets_norm[rank_detectado])  # copia

    # Passo 2: nome so no bucket
    for (_, texto, conf) in resultados:
        if conf < 0.3:
            continue
        texto_norm = _normalizar(texto)
        for nome in nomes_alvo:
            if nome in texto_norm or texto_norm in nome:
                return nome, rank_detectado

    return None, rank_detectado

# ─────────────────────────────────────────────
#  LOOP DE CAPTURA
# ─────────────────────────────────────────────

def loop_captura(get_regiao):
    with mss.mss() as sct:
        while True:
            if not estado["rodando"]:
                time.sleep(0.1); continue
            if estado["pausado_por_input"]:
                time.sleep(0.05); continue
            if time.perf_counter() - estado["ultimo_clique"] < COOLDOWN_APOS_CLIQUE:
                time.sleep(0.05); continue

            regiao = get_regiao()
            if regiao is None:
                time.sleep(0.1); continue

            t0 = time.perf_counter()
            try:
                img = np.array(sct.grab(regiao))
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                nome, rank = extrair_nome_rank(img_bgr)
                
                if estado["log_detalhado"]:
                    fila_log.put(f"[OCR] {time.perf_counter()-t0:.2f}s | nome={nome} rank={rank}")

                if nome and target_ativo(rank, nome):
                    threading.Thread(target=executar_acao, args=(nome, rank),
                                     daemon=True).start()
            except Exception as e:
                fila_log.put(f"[ERRO captura] {e}")

            time.sleep(max(0, INTERVALO_CAPTURA - (time.perf_counter() - t0)))

# ─────────────────────────────────────────────
#  INPUT HUMANO
# ─────────────────────────────────────────────

_ultimo_input_humano = 0.0

def _on_move(x, y):
    global _ultimo_input_humano
    if estado["clique_script_ativo"]: return
    _ultimo_input_humano = time.perf_counter()
    if estado["rodando"]: estado["pausado_por_input"] = True

def _on_click(x, y, button, pressed):
    global _ultimo_input_humano
    if estado["clique_script_ativo"] or not pressed: return
    _ultimo_input_humano = time.perf_counter()
    if estado["rodando"]: estado["pausado_por_input"] = True

def _on_key(key):
    global _ultimo_input_humano
    if estado["clique_script_ativo"]: return
    _ultimo_input_humano = time.perf_counter()
    if estado["rodando"]: estado["pausado_por_input"] = True

def _monitor_retomada():
    while True:
        if estado["pausado_por_input"]:
            if time.perf_counter() - _ultimo_input_humano > 1.0:
                estado["pausado_por_input"] = False
                fila_log.put("[INFO] Retomado.")
        time.sleep(0.2)

def iniciar_listeners():
    pmouse.Listener(on_move=_on_move, on_click=_on_click, daemon=True).start()
    pkeyboard.Listener(on_press=_on_key, daemon=True).start()
    threading.Thread(target=_monitor_retomada, daemon=True).start()

# ─────────────────────────────────────────────
#  INTERFACE GRAFICA
# ─────────────────────────────────────────────

class App(tk.Tk):
    LARGURA        = 420
    ALTURA_CAPTURA = 70
    ALTURA_PAINEL  = 135
    COR_OVERLAY    = "#00FF88"
    COR_BG         = "#0A0A0A"
    COR_TEXTO      = "#CCCCCC"
    COR_CHROMA     = "#000001" # Nova cor que será 100% transparente

    def _atualizar_toggles(self):
        estado["log_detalhado"] = self.var_log.get()
        estado["usar_telegram"] = self.var_tg.get()

    def __init__(self):
        super().__init__()
        self.title("Card Scanner")
        self.geometry(f"{self.LARGURA}x{self.ALTURA_CAPTURA + self.ALTURA_PAINEL}")
        self.configure(bg=self.COR_BG)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.88)
        
        # Define a cor escolhida como invisível no Windows
        self.attributes("-transparentcolor", self.COR_CHROMA) 
        
        self._drag_x = self._drag_y = 0
        self.var_log = tk.BooleanVar(value=False)
        self.var_tg  = tk.BooleanVar(value=True)
        self._build_ui()
        self._poll_log()

    def _build_ui(self):
        barra = tk.Frame(self, bg="#111111", height=22, cursor="fleur")
        barra.pack(fill="x")
        barra.bind("<ButtonPress-1>", self._drag_start)
        barra.bind("<B1-Motion>",     self._drag_move)
        tk.Label(barra, text="◈ CARD SCANNER", bg="#111111",
                 fg=self.COR_OVERLAY, font=("Consolas", 9, "bold")).pack(side="left", padx=6)
        btn_x = tk.Label(barra, text="✕", bg="#111111", fg="#FF4444",
                         font=("Consolas", 10, "bold"), cursor="hand2")
        btn_x.pack(side="right", padx=6)
        btn_x.bind("<Button-1>", lambda e: self.destroy())

        # Aqui mudamos o 'bg' do Canvas para a cor do chroma key
        self.canvas = tk.Canvas(self, width=self.LARGURA, height=self.ALTURA_CAPTURA,
                                bg=self.COR_CHROMA, highlightthickness=0)
        self.canvas.pack()
        
        # A borda verde pontilhada continua aparecendo porque tem a cor COR_OVERLAY
        self.canvas.create_rectangle(1, 1, self.LARGURA-2, self.ALTURA_CAPTURA-2,
                                     outline=self.COR_OVERLAY, width=2, dash=(4, 4))
        
        # OBS: Eu comentei o texto "[ AREA DE CAPTURA ]" para não atrapalhar o OCR do bot!
        # self.canvas.create_text(self.LARGURA//2, self.ALTURA_CAPTURA//2,
        #                         text="[ AREA DE CAPTURA ]",
        #                         fill="#334433", font=("Consolas", 8))

        painel = tk.Frame(self, bg=self.COR_BG)
        painel.pack(fill="x", padx=6, pady=4)

        linha1 = tk.Frame(painel, bg=self.COR_BG)
        linha1.pack(fill="x")

        self.btn = tk.Button(linha1, text="▶  START", bg="#003322", fg=self.COR_OVERLAY,
                             font=("Consolas", 10, "bold"), relief="flat",
                             activebackground="#004433", activeforeground=self.COR_OVERLAY,
                             cursor="hand2", width=12, command=self._toggle)
        self.btn.pack(side="left", padx=(0, 8))

        self.lbl_status = tk.Label(linha1, text="● PARADO", bg=self.COR_BG,
                                   fg="#FF4444", font=("Consolas", 9))
        self.lbl_status.pack(side="left")

        self.lbl_input = tk.Label(linha1, text="", bg=self.COR_BG,
                                  fg="#FFAA00", font=("Consolas", 8))
        self.lbl_input.pack(side="right", padx=4)

        linha2 = tk.Frame(painel, bg=self.COR_BG)
        linha2.pack(fill="x", pady=(4, 0))

        chk_log = tk.Checkbutton(linha2, text="Logs OCR", variable=self.var_log, command=self._atualizar_toggles,
                                 bg=self.COR_BG, fg=self.COR_TEXTO, selectcolor="#111111", activebackground=self.COR_BG, activeforeground=self.COR_TEXTO)
        chk_log.pack(side="left")

        chk_tg = tk.Checkbutton(linha2, text="Telegram", variable=self.var_tg, command=self._atualizar_toggles,
                                bg=self.COR_BG, fg=self.COR_TEXTO, selectcolor="#111111", activebackground=self.COR_BG, activeforeground=self.COR_TEXTO)
        chk_tg.pack(side="left", padx=10)

        log_frame = tk.Frame(self, bg=self.COR_BG)
        log_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.log = tk.Text(log_frame, bg="#0D0D0D", fg=self.COR_TEXTO,
                           font=("Consolas", 7), height=4, relief="flat",
                           state="disabled", wrap="word")
        scroll = tk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        self.log.tag_config("acao",     foreground=self.COR_OVERLAY)
        self.log.tag_config("telegram", foreground="#00AAFF")
        self.log.tag_config("confirm",  foreground="#FFD700")
        self.log.tag_config("lista",    foreground="#FF8800")
        self.log.tag_config("erro",     foreground="#FF4444")
        self.log.tag_config("ocr",      foreground="#444444")

    def _drag_start(self, e): self._drag_x, self._drag_y = e.x, e.y
    def _drag_move(self, e):
        self.geometry(f"+{self.winfo_x()+e.x-self._drag_x}+{self.winfo_y()+e.y-self._drag_y}")

    def _toggle(self):
        estado["rodando"] = not estado["rodando"]
        if estado["rodando"]:
            estado["pausado_por_input"] = False
            self.btn.config(text="⏸  PAUSE", bg="#002211")
            self.lbl_status.config(text="● RODANDO", fg=self.COR_OVERLAY)
            fila_log.put("[INFO] Scanner iniciado.")
        else:
            self.btn.config(text="▶  START", bg="#003322")
            self.lbl_status.config(text="● PARADO", fg="#FF4444")
            fila_log.put("[INFO] Scanner pausado.")

    def get_regiao(self):
        try:
            return {
                "left":   self.winfo_rootx() + 2,
                "top":    self.winfo_rooty() + 22 + 2,
                "width":  self.LARGURA - 4,
                "height": self.ALTURA_CAPTURA - 4,
            }
        except Exception:
            return None

    def _poll_log(self):
        try:
            while True:
                msg = fila_log.get_nowait()
                self._append_log(msg)
                self.lbl_input.config(
                    text="⏸ input detectado" if estado["pausado_por_input"] else "")
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _append_log(self, msg: str):
        self.log.configure(state="normal")
        if   "[ACAO]"     in msg: tag = "acao"
        elif "[TELEGRAM]" in msg: tag = "telegram"
        elif "[CONFIRM]"  in msg: tag = "confirm"
        elif "[LISTA]"    in msg: tag = "lista"
        elif "[ERRO"      in msg: tag = "erro"
        else:                     tag = "ocr"
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        linhas = int(self.log.index("end-1c").split(".")[0])
        if linhas > 200:
            self.log.delete("1.0", f"{linhas-200}.0")
        self.log.configure(state="disabled")

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    app = App()
    _carregar_removidos()
    iniciar_listeners()
    threading.Thread(target=loop_captura,  args=(app.get_regiao,), daemon=True).start()
    threading.Thread(target=_loop_polling, daemon=True).start()
    app.mainloop()

if __name__ == "__main__":
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE    = 0
    main()
