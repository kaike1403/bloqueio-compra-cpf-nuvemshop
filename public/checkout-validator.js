const API_URL = "https://bloqueio-compra-cpf-nuvemshop.onrender.com/api/validar-checkout";
const TEMPO_LIMITE_API_MS = 10000;
const ATRASO_VALIDACAO_MS = 120;
const INTERVALO_REAPLICACAO_MS = 1000;
function limparCpf(valor) {
    return String(valor ?? "").replace(/\D/g, "");
}
function enviarResultado(nube, permitido, mensagem) {
    if (permitido) {
        nube.send("cart:validate", () => ({
            cart: {
                validation: {
                    status: "success",
                },
            },
        }));
        return;
    }
    nube.send("cart:validate", () => ({
        cart: {
            validation: {
                status: "fail",
                reason: mensagem ||
                    "Não foi possível validar esta compra.",
            },
        },
    }));
}
export function App(nube) {
    let validacaoEmAndamento = false;
    let chaveEmValidacao = "";
    let ultimaChaveValidada = "";
    let ultimoResultado = null;
    let contadorValidacao = 0;
    let controladorAtual = null;
    let temporizadorValidacao = null;
    nube.send("config:set", () => ({
        config: {
            has_cart_validation: true,
        },
    }));
    function obterSnapshot() {
        const estado = nube.getState();
        const cpf = limparCpf(estado.customer?.billing_address?.id_number);
        const itens = estado.cart.items.map((item) => ({
            product_id: String(item.product_id),
            variant_id: String(item.variant_id),
            quantity: Number(item.quantity ?? 0),
            name: String(item.name ?? ""),
        }));
        const chave = JSON.stringify({
            cpf,
            itens: itens.map((item) => ({
                product_id: item.product_id,
                variant_id: item.variant_id,
                quantity: item.quantity,
            })),
        });
        return {
            cpf,
            itens,
            chave,
        };
    }
    function aplicarResultado(resultado) {
        enviarResultado(nube, resultado.allowed === true, resultado.message);
    }
    function bloquearDuranteValidacao() {
        enviarResultado(nube, false, "Validando CPF e produtos do carrinho...");
    }
    function reaplicarResultadoConhecido() {
        const snapshot = obterSnapshot();
        if (ultimoResultado &&
            snapshot.chave === ultimaChaveValidada) {
            aplicarResultado(ultimoResultado);
            return true;
        }
        return false;
    }
    async function validarCheckout(forcarConsulta = false, bloquearEnquantoConsulta = true) {
        const snapshot = obterSnapshot();
        /*
         * O checkout pode limpar o estado de cart:validate ao
         * trocar pagamento, frete ou ao reconstruir a tela.
         * Mesmo que CPF e itens não tenham mudado, reenviamos o
         * último resultado para manter o botão bloqueado.
         */
        if (!forcarConsulta &&
            ultimoResultado &&
            snapshot.chave === ultimaChaveValidada) {
            aplicarResultado(ultimoResultado);
            return;
        }
        /* Evita requisições duplicadas para o mesmo estado. */
        if (validacaoEmAndamento &&
            snapshot.chave === chaveEmValidacao) {
            if (!reaplicarResultadoConhecido() && bloquearEnquantoConsulta) {
                bloquearDuranteValidacao();
            }
            return;
        }
        if (bloquearEnquantoConsulta) {
            bloquearDuranteValidacao();
        }
        /*
         * Se CPF ou carrinho mudaram, a resposta antiga não pode
         * sobrescrever a validação do estado novo.
         */
        controladorAtual?.abort();
        const numeroValidacao = ++contadorValidacao;
        const controlador = new AbortController();
        controladorAtual = controlador;
        validacaoEmAndamento = true;
        chaveEmValidacao = snapshot.chave;
        const temporizadorApi = setTimeout(() => controlador.abort(), TEMPO_LIMITE_API_MS);
        try {
            const resposta = await fetch(API_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    cpf: snapshot.cpf,
                    items: snapshot.itens,
                }),
                signal: controlador.signal,
            });
            if (!resposta.ok) {
                throw new Error(`Erro HTTP ${resposta.status}`);
            }
            const resultado = (await resposta.json());
            if (numeroValidacao !== contadorValidacao) {
                return;
            }
            ultimaChaveValidada = snapshot.chave;
            ultimoResultado = resultado;
            aplicarResultado(resultado);
            console.log("[Bloqueio CPF] Validação:", resultado.code ?? "SEM_CODIGO");
        }
        catch (erro) {
            if (numeroValidacao !== contadorValidacao) {
                return;
            }
            if (erro instanceof DOMException &&
                erro.name === "AbortError") {
                console.warn("[Bloqueio CPF] Validação cancelada ou expirada.");
            }
            else {
                console.error("[Bloqueio CPF] Erro ao consultar API:", erro);
            }
            /*
             * Fail-closed: uma falha da API não pode liberar uma
             * compra que deveria estar bloqueada.
             */
            const resultadoIndisponivel = {
                allowed: false,
                code: "VALIDATION_UNAVAILABLE",
                message: "Não foi possível validar esta compra agora. " +
                    "Aguarde alguns segundos e tente novamente.",
            };
            ultimaChaveValidada = snapshot.chave;
            ultimoResultado = resultadoIndisponivel;
            aplicarResultado(resultadoIndisponivel);
        }
        finally {
            clearTimeout(temporizadorApi);
            if (numeroValidacao === contadorValidacao) {
                validacaoEmAndamento = false;
                chaveEmValidacao = "";
                controladorAtual = null;
            }
        }
    }
    function agendarValidacao(forcarConsulta = false, bloquearEnquantoConsulta = true, atraso = ATRASO_VALIDACAO_MS) {
        if (temporizadorValidacao !== null) {
            clearTimeout(temporizadorValidacao);
        }
        temporizadorValidacao = setTimeout(() => {
            temporizadorValidacao = null;
            void validarCheckout(forcarConsulta, bloquearEnquantoConsulta);
        }, atraso);
    }
    function tratarReconstrucaoDoCheckout(forcarConsulta = true) {
        /* Reaplica imediatamente o bloqueio já conhecido. */
        const reaplicado = reaplicarResultadoConhecido();
        if (!reaplicado) {
            bloquearDuranteValidacao();
        }
        /*
         * Consulta novamente porque o status do pedido pode ter
         * mudado no backend enquanto o cliente permaneceu aberto
         * no checkout.
         */
        agendarValidacao(forcarConsulta, true);
        /*
         * Algumas partes do checkout são reconstruídas depois do
         * evento. Reaplicamos novamente após a renderização.
         */
        setTimeout(() => {
            if (!reaplicarResultadoConhecido()) {
                agendarValidacao(false, true, 0);
            }
        }, 450);
    }
    nube.on("checkout:ready", () => {
        tratarReconstrucaoDoCheckout();
    });
    nube.on("page:loaded", () => {
        tratarReconstrucaoDoCheckout();
    });
    nube.on("cart:update", () => {
        agendarValidacao(false, true);
    });
    nube.on("customer:update", () => {
        agendarValidacao(false, true, 250);
    });
    nube.on("shipping:update", () => {
        tratarReconstrucaoDoCheckout();
    });
    nube.on("payment:update", () => {
        tratarReconstrucaoDoCheckout();
    });
    nube.on("location:updated", () => {
        tratarReconstrucaoDoCheckout(false);
    });
    /*
     * Proteção adicional: se o checkout limpar a validação sem
     * emitir um evento documentado, um resultado de bloqueio é
     * reaplicado periodicamente. Isso não chama a API.
     */
    setInterval(() => {
        if (ultimoResultado?.allowed === false) {
            reaplicarResultadoConhecido();
        }
    }, INTERVALO_REAPLICACAO_MS);
    /*
     * Fallback para carregamentos em que checkout:ready já foi
     * emitido antes de o listener ser registrado.
     */
    bloquearDuranteValidacao();
    agendarValidacao(true, true, 0);
}
