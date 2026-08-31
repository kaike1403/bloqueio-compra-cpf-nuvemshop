import type { NubeSDK } from "@tiendanube/nube-sdk-types";

const API_ORIGIN = "https://bloqueio-compra-cpf-nuvemshop.onrender.com";
const TOKEN_PATH = "/_nsv/a646e9ba169dc7f01c5845c5e6019d24";
const VALIDATE_PATH = "/_nsv/0f6958d6a5d10f3bb4b28ce4c3c302dc";
const TOKEN_URL = `${API_ORIGIN}${TOKEN_PATH}`;
const API_URL = `${API_ORIGIN}${VALIDATE_PATH}`;

const TEMPO_LIMITE_API_MS = 10_000;
const ATRASO_VALIDACAO_MS = 120;
const INTERVALO_REAPLICACAO_MS = 250;
const MARGEM_RENOVACAO_TOKEN_MS = 30_000;
const MENSAGEM_VALIDANDO = "Validando CPF e produtos do carrinho...";
const MENSAGEM_TRAVA_INTERACOES = "Validando sua compra. Aguarde alguns instantes...";

const STATUS_SEGURANCA_BLOQUEANTES = new Set([400, 401, 403, 413, 422, 429]);

type ItemCheckout = {
  product_id: string;
  variant_id: string;
  quantity: number;
  name: string;
};

type RespostaValidacao = {
  allowed: boolean;
  code?: string;
  message?: string;
};

type SnapshotCheckout = {
  cpf: string;
  itens: ItemCheckout[];
  storeId: string;
  sessionId: string;
  chave: string;
};

class ErroSegurancaCheckout extends Error {
  status: number;

  constructor(status: number, mensagem: string) {
    super(mensagem);
    this.status = status;
    this.name = "ErroSegurancaCheckout";
  }
}

function limparCpf(valor: unknown): string {
  return String(valor ?? "").replace(/\D/g, "");
}

function validarCpfLocal(cpf: unknown): boolean {
  const valor = limparCpf(cpf);
  if (valor.length !== 11 || /^(\d)\1{10}$/.test(valor)) return false;

  for (const tamanho of [9, 10]) {
    let soma = 0;
    for (let indice = 0; indice < tamanho; indice += 1) {
      soma += Number(valor[indice]) * (tamanho + 1 - indice);
    }
    let digito = (soma * 10) % 11;
    if (digito === 10) digito = 0;
    if (digito !== Number(valor[tamanho])) return false;
  }

  return true;
}

function obterCpfDoEstado(estado: unknown): string {
  const raiz = (estado ?? {}) as Record<string, any>;
  const customer = raiz.customer ?? {};
  const billing = customer.billing_address ?? {};
  const shipping = customer.shipping_address ?? {};
  const candidatos: unknown[] = [
    customer.cpf_cnpj,
    customer.identification,
    customer.identification_number,
    customer.id_number,
    customer.document,
    billing.id_number,
    billing.identification,
    billing.cpf_cnpj,
    shipping.id_number,
    shipping.identification,
    shipping.cpf_cnpj,
  ];

  for (const candidato of candidatos) {
    const cpf = limparCpf(candidato);
    if (cpf.length === 11 && validarCpfLocal(cpf)) return cpf;
  }

  // Retorna também um CPF de 11 dígitos inválido para que o fluxo possa
  // bloqueá-lo explicitamente como INVALID_CPF.
  for (const candidato of candidatos) {
    const cpf = limparCpf(candidato);
    if (cpf.length === 11) return cpf;
  }

  return "";
}

function enviarResultado(nube: NubeSDK, permitido: boolean, mensagem?: string): void {
  if (permitido === true) {
    nube.send("cart:validate", () => ({
      cart: { validation: { status: "success" } },
    }));
    return;
  }

  nube.send("cart:validate", () => ({
    cart: {
      validation: {
        status: "fail",
        reason: mensagem || "Não foi possível validar esta compra.",
      },
    },
  }));
}

function hashBase36(valor: string): string {
  let hash = 5381;
  for (let indice = 0; indice < valor.length; indice += 1) {
    hash = (hash * 33) ^ valor.charCodeAt(indice);
  }
  return (hash >>> 0).toString(36);
}

function componenteModalValidacao(): any {
  // NubeSDK roda em Web Worker e não permite document/window. O slot
  // modal_content é a forma oficial de criar um backdrop sobre o checkout.
  const appIdBruto = String((self as any).__APP_DATA__?.id ?? "cpfcheckout");
  const appId = appIdBruto.replace(/[^a-zA-Z0-9]/g, "") || "cpfcheckout";

  return {
    type: "txt",
    children: MENSAGEM_TRAVA_INTERACOES,
    modifiers: ["bold"],
    __internalId: `txt-${appId}-${hashBase36(MENSAGEM_TRAVA_INTERACOES)}`,
  };
}

export function App(nube: NubeSDK): void {
  let validacaoEmAndamento = false;
  let chaveEmValidacao = "";
  let ultimaChaveValidada = "";
  let ultimoResultado: RespostaValidacao | null = null;
  let contadorValidacao = 0;
  let controladorAtual: AbortController | null = null;
  let temporizadorValidacao: ReturnType<typeof setTimeout> | null = null;
  let checkoutToken = "";
  let checkoutTokenExpiraEmMs = 0;
  let checkoutBloqueado = true;
  let motivoBloqueioAtual = MENSAGEM_VALIDANDO;
  let interacoesBloqueadas = false;

  function obterSnapshot(): SnapshotCheckout {
    const estado = nube.getState() as any;
    const cpf = obterCpfDoEstado(estado);
    const storeId = String(estado?.store?.id ?? "");
    const sessionId = String(estado?.session?.id ?? "");
    const itensOriginais = Array.isArray(estado?.cart?.items) ? estado.cart.items : [];
    const itens: ItemCheckout[] = itensOriginais.map((item: any) => ({
      product_id: String(item?.product_id ?? ""),
      variant_id: String(item?.variant_id ?? ""),
      quantity: Number(item?.quantity ?? 0),
      name: String(item?.name ?? ""),
    }));

    const chave = JSON.stringify({
      cpf,
      storeId,
      sessionId,
      itens: itens.map((item) => ({
        product_id: item.product_id,
        variant_id: item.variant_id,
        quantity: item.quantity,
      })),
    });

    return { cpf, itens, storeId, sessionId, chave };
  }

  function deveTravarInteracoes(snapshot: SnapshotCheckout): boolean {
    // Não bloqueia campos enquanto o cliente ainda está preenchendo o CPF.
    // O botão de finalizar continua bloqueado por cart:validate desde o início.
    return snapshot.cpf.length === 11;
  }

  function bloquearInteracoes(snapshot: SnapshotCheckout): void {
    if (!deveTravarInteracoes(snapshot)) {
      if (interacoesBloqueadas) {
        interacoesBloqueadas = false;
        nube.clearSlot("modal_content");
      }
      return;
    }

    interacoesBloqueadas = true;
    nube.render("modal_content", componenteModalValidacao());
  }

  function liberarInteracoes(): void {
    if (!interacoesBloqueadas) return;
    interacoesBloqueadas = false;
    nube.clearSlot("modal_content");
  }

  function aplicarResultado(resultado: RespostaValidacao): void {
    // A validação terminou. A página volta a ser interativa mesmo quando a
    // regra de negócio mantém somente o botão de finalizar bloqueado.
    liberarInteracoes();

    if (resultado?.allowed === true) {
      checkoutBloqueado = false;
      motivoBloqueioAtual = "";
      enviarResultado(nube, true);
      return;
    }

    checkoutBloqueado = true;
    motivoBloqueioAtual =
      resultado?.message || "Esta compra não foi autorizada pela validação.";
    enviarResultado(nube, false, motivoBloqueioAtual);
  }

  function bloquearDuranteValidacao(snapshot: SnapshotCheckout): void {
    checkoutBloqueado = true;
    motivoBloqueioAtual = MENSAGEM_VALIDANDO;
    enviarResultado(nube, false, MENSAGEM_VALIDANDO);
    bloquearInteracoes(snapshot);
  }

  function liberarPorIndisponibilidade(
    _snapshot: SnapshotCheckout,
    codigo = "VALIDATION_UNAVAILABLE_ALLOWED",
  ): void {
    const resultado: RespostaValidacao = {
      allowed: true,
      code: codigo,
      message: "A validação está temporariamente indisponível. O checkout foi liberado.",
    };

    // Fail-open técnico não vira autorização cacheável. Um novo evento do
    // checkout tentará validar novamente.
    ultimaChaveValidada = "";
    ultimoResultado = null;
    aplicarResultado(resultado);
  }

  function reaplicarBloqueioAtual(): void {
    if (checkoutBloqueado) {
      enviarResultado(nube, false, motivoBloqueioAtual || MENSAGEM_VALIDANDO);
    }
  }

  async function obterTokenCheckout(
    snapshot: SnapshotCheckout,
    signal: AbortSignal,
  ): Promise<string> {
    if (
      checkoutToken &&
      Date.now() + MARGEM_RENOVACAO_TOKEN_MS < checkoutTokenExpiraEmMs
    ) {
      return checkoutToken;
    }

    const resposta = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        store_id: snapshot.storeId,
        session_id: snapshot.sessionId,
      }),
      signal,
    });

    const corpo = await resposta.json().catch(() => ({})) as any;
    if (!resposta.ok || !corpo.success || !corpo.token) {
      throw new ErroSegurancaCheckout(
        resposta.status,
        corpo.message || "Não foi possível autenticar o checkout.",
      );
    }

    checkoutToken = corpo.token;
    checkoutTokenExpiraEmMs = Number(corpo.expires_at ?? 0) * 1000;
    return checkoutToken;
  }

  async function validarCheckout(forcarConsulta = false): Promise<void> {
    const snapshot = obterSnapshot();

    if (!forcarConsulta && ultimoResultado && snapshot.chave === ultimaChaveValidada) {
      aplicarResultado(ultimoResultado);
      return;
    }

    if (validacaoEmAndamento && snapshot.chave === chaveEmValidacao) {
      reaplicarBloqueioAtual();
      bloquearInteracoes(snapshot);
      return;
    }

    bloquearDuranteValidacao(snapshot);
    controladorAtual?.abort();

    const numeroValidacao = ++contadorValidacao;
    const controlador = new AbortController();
    controladorAtual = controlador;
    validacaoEmAndamento = true;
    chaveEmValidacao = snapshot.chave;
    const temporizadorApi = setTimeout(
      () => controlador.abort(),
      TEMPO_LIMITE_API_MS,
    );

    try {
      if (snapshot.cpf && !validarCpfLocal(snapshot.cpf)) {
        const resultado: RespostaValidacao = {
          allowed: false,
          code: "INVALID_CPF",
          message: "Informe um CPF válido para continuar a compra.",
        };
        ultimaChaveValidada = snapshot.chave;
        ultimoResultado = resultado;
        aplicarResultado(resultado);
        return;
      }

      if (!snapshot.storeId || !snapshot.sessionId) {
        liberarPorIndisponibilidade(
          snapshot,
          "CHECKOUT_CONTEXT_UNAVAILABLE_ALLOWED",
        );
        return;
      }

      const token = await obterTokenCheckout(snapshot, controlador.signal);
      const resposta = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Store-ID": snapshot.storeId,
          "X-Checkout-Session": snapshot.sessionId,
          "X-Checkout-Token": token,
        },
        body: JSON.stringify({ cpf: snapshot.cpf, items: snapshot.itens }),
        signal: controlador.signal,
      });

      const resultado = await resposta.json().catch(() => ({})) as RespostaValidacao;

      if (!resposta.ok) {
        if (STATUS_SEGURANCA_BLOQUEANTES.has(resposta.status)) {
          checkoutToken = "";
          checkoutTokenExpiraEmMs = 0;
          throw new ErroSegurancaCheckout(
            resposta.status,
            resultado.message || "A validação de segurança recusou a solicitação.",
          );
        }

        // 404/408/5xx e equivalentes são tratados como indisponibilidade
        // técnica e seguem a política fail-open solicitada.
        throw new Error(`Erro HTTP ${resposta.status}`);
      }

      if (numeroValidacao !== contadorValidacao) return;

      ultimaChaveValidada = snapshot.chave;
      ultimoResultado = resultado;
      aplicarResultado(resultado);
      console.log("[Bloqueio CPF] Validação:", resultado.code ?? "SEM_CODIGO");
    } catch (erro) {
      if (numeroValidacao !== contadorValidacao) return;

      if (erro instanceof ErroSegurancaCheckout) {
        if (STATUS_SEGURANCA_BLOQUEANTES.has(Number(erro.status))) {
          const resultado: RespostaValidacao = {
            allowed: false,
            code: "VALIDATION_SECURITY_BLOCKED",
            message:
              Number(erro.status) === 429
                ? "Muitas tentativas de validação. Aguarde alguns instantes."
                : "Não foi possível autenticar esta validação de checkout.",
          };
          ultimaChaveValidada = snapshot.chave;
          ultimoResultado = resultado;
          aplicarResultado(resultado);
          return;
        }

        liberarPorIndisponibilidade(snapshot);
        return;
      }

      if (erro instanceof DOMException && erro.name === "AbortError") {
        console.warn("[Bloqueio CPF] Validação cancelada ou expirada.");
      } else {
        console.error("[Bloqueio CPF] Erro ao consultar API:", erro);
      }

      liberarPorIndisponibilidade(snapshot);
    } finally {
      clearTimeout(temporizadorApi);
      if (numeroValidacao === contadorValidacao) {
        validacaoEmAndamento = false;
        chaveEmValidacao = "";
        controladorAtual = null;
      }
    }
  }

  function agendarValidacao(
    forcarConsulta = false,
    atraso = ATRASO_VALIDACAO_MS,
  ): void {
    if (temporizadorValidacao !== null) clearTimeout(temporizadorValidacao);
    temporizadorValidacao = setTimeout(() => {
      temporizadorValidacao = null;
      void validarCheckout(forcarConsulta);
    }, atraso);
  }

  function bloquearEAgendar(
    forcarConsulta = false,
    atraso = ATRASO_VALIDACAO_MS,
  ): void {
    const snapshot = obterSnapshot();
    bloquearDuranteValidacao(snapshot);
    agendarValidacao(forcarConsulta, atraso);
  }

  function tratarReconstrucaoDoCheckout(forcarConsulta = true): void {
    const snapshot = obterSnapshot();
    bloquearDuranteValidacao(snapshot);
    agendarValidacao(forcarConsulta);

    setTimeout(() => {
      if (checkoutBloqueado) reaplicarBloqueioAtual();
      if (interacoesBloqueadas) nube.render("modal_content", componenteModalValidacao());
    }, 50);

    setTimeout(() => {
      if (checkoutBloqueado) reaplicarBloqueioAtual();
      if (interacoesBloqueadas) nube.render("modal_content", componenteModalValidacao());
    }, 250);
  }

  // 1) O botão de finalizar nasce bloqueado antes de qualquer fetch/debounce.
  nube.send("config:set", () => ({ config: { has_cart_validation: true } }));
  enviarResultado(nube, false, MENSAGEM_VALIDANDO);

  // 2) Se já existe CPF completo no estado, também bloqueia as interações com
  // o checkout usando modal_content/backdrop enquanto a API responde.
  bloquearInteracoes(obterSnapshot());

  for (const atraso of [0, 50, 150]) {
    setTimeout(() => {
      if (checkoutBloqueado) reaplicarBloqueioAtual();
      if (interacoesBloqueadas) nube.render("modal_content", componenteModalValidacao());
    }, atraso);
  }

  nube.on("checkout:ready", () => tratarReconstrucaoDoCheckout(true));
  nube.on("page:loaded", () => tratarReconstrucaoDoCheckout(true));
  nube.on("cart:update", () => bloquearEAgendar(false));
  nube.on("customer:update", () => bloquearEAgendar(false, 120));
  nube.on("shipping:update", () => tratarReconstrucaoDoCheckout(true));
  nube.on("payment:update", () => tratarReconstrucaoDoCheckout(true));
  nube.on("location:updated", () => bloquearEAgendar(false, 0));

  // modal_content pode ser fechado pelo usuário com backdrop/Esc. Enquanto a
  // validação ainda está em andamento, reabrimos imediatamente. Assim que o
  // backend responde (permitindo, bloqueando ou fail-open), o modal é limpo.
  nube.on("custom:modal:close", () => {
    if (!interacoesBloqueadas) return;
    setTimeout(() => {
      if (interacoesBloqueadas) {
        nube.render("modal_content", componenteModalValidacao());
      }
    }, 0);
  });

  // Watchdog para reconstruções silenciosas do checkout. Não chama a API.
  setInterval(() => {
    if (checkoutBloqueado) reaplicarBloqueioAtual();
    if (interacoesBloqueadas) {
      nube.render("modal_content", componenteModalValidacao());
    }
  }, INTERVALO_REAPLICACAO_MS);

  agendarValidacao(true, 0);
}
