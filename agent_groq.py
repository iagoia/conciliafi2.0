from antigravity import Agent, GenerationConfig
from antigravity.tools import tool

# ==========================================
# TRAVA 1: O ESTRANGULADOR DE LOGS (Evita ralo de Input)
# ==========================================
def truncar_saida(texto: str, limite_caracteres: int = 1500) -> str:
    """Garante que nenhuma ferramenta devolva textos gigantes pro LLM ler."""
    if len(texto) > limite_caracteres:
        return texto[-limite_caracteres:] + "\n[AVISO: Log truncado para economizar memória.]"
    return texto

@tool
def consultar_log_bomba_combustivel(id_posto: str) -> str:
    """Consulta os logs de comunicação com a pista."""
    # Simulação da sua chamada real de banco
    log_bruto = f"Conectando ao posto {id_posto}...\n" * 200 + "ERRO: COM4 Timeout"
    
    # NUNCA retorne o log_bruto direto. Passe pelo estrangulador:
    return truncar_saida(log_bruto)


# ==========================================
# TRAVA 2: AGENTE OPERÁRIO (Custo Médio, Limite de Erros)
# ==========================================
suporte_tecnico = Agent(
    name="Especialista_LUKOS",
    instructions=(
        "Você é o suporte N2. Leia os logs e resolva os BOs da pista. "
        "Seja cirúrgico. Não enrole na resposta."
    ),
    tools=[consultar_log_bomba_combustivel],
    config=GenerationConfig(
        # Substituído 'gemini-1.5-flash' pelo Llama 3.1 70B ou Llama 3.3 70B da Groq
        model="llama-3.3-70b-versatile",    # Ou "llama-3.1-70b-versatile"
        thinking_level="MEDIUM",     
        max_turns=3                  # SE ELE ERRAR A FERRAMENTA 3 VEZES, O SDK MATA A EXECUÇÃO.
    )
)


# ==========================================
# TRAVA 3: AGENTE RECEPCIONISTA (Custo Mínimo, Zero Enrolação)
# ==========================================
triagem_main = Agent(
    name="Triagem_Nivel1",
    instructions=(
        "Você é a triagem. Identifique se o problema é técnico (bomba/conexão) "
        "ou financeiro (conciliação). Apenas repasse para o subagente, sem conversar muito."
    ),
    sub_agents=[suporte_tecnico],
    config=GenerationConfig(
        # Substituído 'gemini-1.5-flash-8b' pelo Llama 3.1 8B da Groq
        model="llama-3.1-8b-instant",        
        thinking_level="MINIMAL",    # Ele não precisa "pensar", só precisa rotear.
        max_turns=1                  # Ele não pode usar ferramentas, só pode tomar 1 decisão e passar o bastão.
    )
)

# ==========================================
# EXECUÇÃO DO FLUXO ECONÔMICO
# ==========================================
async def rodar_fluxo_barato():
    chamado = "A bomba 2 do posto perdeu conexão com o sistema, me ajuda!"
    
    print("Iniciando atendimento (Modo Economia com Groq Llama)...\n")
    
    resposta = await triagem_main.generate_async(chamado)
    
    # Corrigido o loop de resposta (estava iterando sobre a variável indefinida 'response')
    async for chunk in resposta:
        print(chunk.text, end="")
        
    print(f"\n\n[INFO] Tokens Gastos na Brincadeira: {resposta.usage_metadata.total_token_count}")

# import asyncio; asyncio.run(rodar_fluxo_barato())
