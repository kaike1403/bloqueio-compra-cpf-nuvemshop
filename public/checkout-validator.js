const API_URL = "https://bloqueio-compra-cpf-nuvemshop.onrender.com/api/validar-checkout";
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
    let ultimaChaveValidada = "";
    let contadorValidacao = 0;
    nube.send("config:set", () => ({
        config: {
            has_cart_validation: true,
        },
    }));
    async function validarCheckout() {
        const numeroValidacao = ++contadorValidacao;
        const estado = nube.getState();
        const cpf = limparCpf(estado.customer?.billing_address?.id_number);
        const itens = estado.cart.items.map((item) => ({
            product_id: String(item.product_id),
            variant_id: String(item.variant_id),
            quantity: Number(item.quantity ?? 0),
            name: String(item.name ?? ""),
        }));
        const chaveAtual = JSON.stringify({
            cpf,
            itens: itens.map((item) => ({
                product_id: item.product_id,
                variant_id: item.variant_id,
                quantity: item.quantity,
            })),
        });
        if (chaveAtual === ultimaChaveValidada &&
            !validacaoEmAndamento) {
            return;
        }
        ultimaChaveValidada = chaveAtual;
        validacaoEmAndamento = true;
        const controlador = new AbortController();
        const temporizador = setTimeout(() => controlador.abort(), 10000);
        try {
            const resposta = await fetch(API_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    cpf,
                    items: itens,
                }),
                signal: controlador.signal,
            });
            if (!resposta.ok) {
                throw new Error(`Erro HTTP ${resposta.status}`);
            }
            const resultado = (await resposta.json());
            /*
             * Ignora respostas antigas quando uma nova validação
             * começou antes da requisição anterior terminar.
             */
            if (numeroValidacao !== contadorValidacao) {
                return;
            }
            enviarResultado(nube, resultado.allowed === true, resultado.message);
            console.log("[Bloqueio CPF] Resultado:", resultado);
        }
        catch (erro) {
            console.error("[Bloqueio CPF] Erro ao consultar API:", erro);
            /*
             * Estratégia segura:
             * quando o carrinho possui produto controlado e a API
             * não responde, bloqueamos temporariamente a progressão.
             *
             * Nesta primeira versão, como o script ainda não sabe
             * localmente quais produtos são controlados, bloqueamos
             * apenas até que a API volte a responder.
             */
            enviarResultado(nube, false, "Não foi possível validar esta compra agora. Aguarde alguns segundos e tente novamente.");
        }
        finally {
            clearTimeout(temporizador);
            if (numeroValidacao === contadorValidacao) {
                validacaoEmAndamento = false;
            }
        }
    }
    nube.on("checkout:ready", () => {
        void validarCheckout();
    });
    nube.on("cart:update", () => {
        void validarCheckout();
    });
    nube.on("customer:update", () => {
        void validarCheckout();
    });
}
