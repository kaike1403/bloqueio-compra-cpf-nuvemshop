const API_BASE_URL =
    "https://bloqueio-compra-cpf-nuvemshop.onrender.com/api";

const API_URL = `${API_BASE_URL}/validar-checkout`;
const TOKEN_URL = `${API_BASE_URL}/checkout-token`;

const TEMPO_LIMITE_API_MS = 10_000;

/*
 * O debounce agora serve SOMENTE para a chamada HTTP.
 * O bloqueio do checkout não espera estes 120ms.
 */
const ATRASO_VALIDACAO_MS = 120;

/*
 * Enquanto não houver autorização explícita do backend,
 * reaplica o bloqueio periodicamente.
 */
const INTERVALO_REAPLICACAO_MS = 250;

const MARGEM_RENOVACAO_TOKEN_MS = 30_000;

const MENSAGEM_VALIDANDO =
    "Validando CPF e produtos do carrinho...";

const MENSAGEM_INDISPONIVEL =
    "Não foi possível validar esta compra agora. Aguarde alguns instantes e tente novamente.";


class ErroSegurancaCheckout extends Error {

    status;

    constructor(status, mensagem) {

        super(mensagem);

        this.status = status;
        this.name = "ErroSegurancaCheckout";
    }
}


function limparCpf(valor) {

    return String(valor ?? "").replace(/\D/g, "");
}


function validarCpfLocal(cpf) {

    const valor = limparCpf(cpf);

    if (
        valor.length !== 11 ||
        /^(\d)\1{10}$/.test(valor)
    ) {

        return false;
    }

    for (const tamanho of [9, 10]) {

        let soma = 0;

        for (
            let indice = 0;
            indice < tamanho;
            indice += 1
        ) {

            soma +=
                Number(valor[indice]) *
                (tamanho + 1 - indice);
        }

        let digito = (soma * 10) % 11;

        if (digito === 10) {

            digito = 0;
        }

        if (
            digito !== Number(valor[tamanho])
        ) {

            return false;
        }
    }

    return true;
}


function obterCpfDoEstado(estado) {

    const raiz = estado ?? {};

    const customer =
        raiz.customer ?? {};

    const billing =
        customer.billing_address ?? {};

    const shipping =
        customer.shipping_address ?? {};


    const candidatos = [

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


    /*
     * Primeiro tenta localizar um CPF
     * matematicamente válido.
     */
    for (const candidato of candidatos) {

        const cpf = limparCpf(

            typeof candidato === "string" ||
            typeof candidato === "number"

                ? candidato

                : ""
        );

        if (
            cpf.length === 11 &&
            validarCpfLocal(cpf)
        ) {

            return cpf;
        }
    }


    /*
     * Se encontrou 11 dígitos mas o CPF é
     * matematicamente inválido, ainda retornamos
     * para que seja bloqueado como INVALID_CPF.
     */
    for (const candidato of candidatos) {

        const cpf = limparCpf(

            typeof candidato === "string" ||
            typeof candidato === "number"

                ? candidato

                : ""
        );

        if (cpf.length === 11) {

            return cpf;
        }
    }


    return "";
}


function enviarResultado(
    nube,
    permitido,
    mensagem
) {

    if (permitido === true) {

        nube.send(
            "cart:validate",
            () => ({

                cart: {

                    validation: {

                        status: "success",
                    },
                },
            })
        );

        return;
    }


    nube.send(
        "cart:validate",
        () => ({

            cart: {

                validation: {

                    status: "fail",

                    reason:
                        mensagem ||
                        "Não foi possível validar esta compra.",
                },
            },
        })
    );
}


export function App(nube) {

    /*
     * ------------------------------------------------
     * ESTADO INTERNO
     * ------------------------------------------------
     */

    let validacaoEmAndamento = false;

    let chaveEmValidacao = "";

    let ultimaChaveValidada = "";

    let ultimoResultado = null;

    let contadorValidacao = 0;

    let controladorAtual = null;

    let temporizadorValidacao = null;


    let checkoutToken = "";

    let checkoutTokenExpiraEmMs = 0;


    /*
     * A regra principal:
     *
     * checkoutBloqueado começa TRUE.
     *
     * Ele somente poderá virar FALSE quando
     * o backend responder explicitamente:
     *
     * allowed === true
     */
    let checkoutBloqueado = true;

    let motivoBloqueioAtual =
        MENSAGEM_VALIDANDO;


    /*
     * =================================================
     * BLOQUEIO IMEDIATO
     * =================================================
     *
     * Estas devem ser as primeiras ações importantes
     * executadas pelo App.
     *
     * Não esperamos:
     *
     * - checkout:ready
     * - cart:update
     * - CPF
     * - token
     * - fetch
     * - API
     * - debounce
     */


    nube.send(
        "config:set",
        () => ({

            config: {

                has_cart_validation: true,
            },
        })
    );


    /*
     * Já inicia em FAIL.
     */
    enviarResultado(
        nube,
        false,
        MENSAGEM_VALIDANDO
    );


    /*
     * Algumas reconstruções internas do checkout
     * podem acontecer praticamente junto com o
     * carregamento do App.
     *
     * Reaplicamos rapidamente.
     */

    setTimeout(
        () => {

            if (checkoutBloqueado) {

                enviarResultado(
                    nube,
                    false,
                    motivoBloqueioAtual
                );
            }
        },
        0
    );


    setTimeout(
        () => {

            if (checkoutBloqueado) {

                enviarResultado(
                    nube,
                    false,
                    motivoBloqueioAtual
                );
            }
        },
        50
    );


    setTimeout(
        () => {

            if (checkoutBloqueado) {

                enviarResultado(
                    nube,
                    false,
                    motivoBloqueioAtual
                );
            }
        },
        150
    );


    /*
     * ------------------------------------------------
     * SNAPSHOT
     * ------------------------------------------------
     */

    function obterSnapshot() {

        const estado =
            nube.getState() ?? {};


        const cpf =
            obterCpfDoEstado(estado);


        const storeId =
            String(
                estado?.store?.id ?? ""
            );


        const sessionId =
            String(
                estado?.session?.id ?? ""
            );


        const itensOriginais =
            Array.isArray(
                estado?.cart?.items
            )

                ? estado.cart.items

                : [];


        const itens =
            itensOriginais.map(
                (item) => ({

                    product_id:
                        String(
                            item?.product_id ?? ""
                        ),

                    variant_id:
                        String(
                            item?.variant_id ?? ""
                        ),

                    quantity:
                        Number(
                            item?.quantity ?? 0
                        ),

                    name:
                        String(
                            item?.name ?? ""
                        ),
                })
            );


        const chave =
            JSON.stringify({

                cpf,

                storeId,

                sessionId,

                itens:
                    itens.map(
                        (item) => ({

                            product_id:
                                item.product_id,

                            variant_id:
                                item.variant_id,

                            quantity:
                                item.quantity,
                        })
                    ),
            });


        return {

            cpf,

            itens,

            storeId,

            sessionId,

            chave,
        };
    }


    /*
     * ------------------------------------------------
     * RESULTADO
     * ------------------------------------------------
     */

    function aplicarResultado(resultado) {

        /*
         * Esta é a ÚNICA condição que libera
         * o checkout.
         */
        if (
            resultado?.allowed === true
        ) {

            checkoutBloqueado = false;

            motivoBloqueioAtual = "";

            enviarResultado(
                nube,
                true,
                ""
            );

            return;
        }


        /*
         * Qualquer outro resultado permanece
         * bloqueado.
         */

        checkoutBloqueado = true;


        motivoBloqueioAtual =
            resultado?.message ||

            "Esta compra não foi autorizada pela validação.";


        enviarResultado(
            nube,
            false,
            motivoBloqueioAtual
        );
    }


    /*
     * ------------------------------------------------
     * BLOQUEIO
     * ------------------------------------------------
     */

    function bloquearDuranteValidacao(
        mensagem = MENSAGEM_VALIDANDO
    ) {

        checkoutBloqueado = true;

        motivoBloqueioAtual =
            mensagem;


        enviarResultado(
            nube,
            false,
            mensagem
        );
    }


    function reaplicarBloqueioAtual() {

        if (!checkoutBloqueado) {

            return false;
        }


        enviarResultado(

            nube,

            false,

            motivoBloqueioAtual ||
            MENSAGEM_VALIDANDO
        );


        return true;
    }


    /*
     * ------------------------------------------------
     * TOKEN
     * ------------------------------------------------
     */

    async function obterTokenCheckout(
        snapshot,
        signal
    ) {

        if (
            checkoutToken &&

            Date.now() +
            MARGEM_RENOVACAO_TOKEN_MS

            <

            checkoutTokenExpiraEmMs
        ) {

            return checkoutToken;
        }


        const resposta =
            await fetch(
                TOKEN_URL,
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json",
                    },

                    body:
                        JSON.stringify({

                            store_id:
                                snapshot.storeId,

                            session_id:
                                snapshot.sessionId,
                        }),

                    signal,
                }
            );


        const corpo =
            await resposta
                .json()
                .catch(
                    () => ({})
                );


        if (
            !resposta.ok ||
            !corpo.success ||
            !corpo.token
        ) {

            throw new ErroSegurancaCheckout(

                resposta.status,

                corpo.message ||

                "Não foi possível autenticar o checkout."
            );
        }


        checkoutToken =
            corpo.token;


        checkoutTokenExpiraEmMs =
            Number(
                corpo.expires_at ?? 0
            ) * 1000;


        return checkoutToken;
    }


    /*
     * ------------------------------------------------
     * VALIDAÇÃO PRINCIPAL
     * ------------------------------------------------
     */

    async function validarCheckout(
        forcarConsulta = false
    ) {

        const snapshot =
            obterSnapshot();


        /*
         * Só reaproveitamos uma validação anterior
         * quando o snapshot é EXATAMENTE o mesmo.
         */

        if (
            !forcarConsulta &&

            ultimoResultado &&

            snapshot.chave ===
            ultimaChaveValidada
        ) {

            aplicarResultado(
                ultimoResultado
            );

            return;
        }


        /*
         * Se já existe uma validação em andamento
         * para este mesmo snapshot, não duplicamos
         * a chamada.
         *
         * Mas o checkout continua BLOQUEADO.
         */

        if (
            validacaoEmAndamento &&

            snapshot.chave ===
            chaveEmValidacao
        ) {

            reaplicarBloqueioAtual();

            return;
        }


        /*
         * =============================================
         * BLOQUEIO ANTES DA API
         * =============================================
         */

        bloquearDuranteValidacao();


        /*
         * Cancela uma validação velha.
         */

        controladorAtual?.abort();


        const numeroValidacao =
            ++contadorValidacao;


        const controlador =
            new AbortController();


        controladorAtual =
            controlador;


        validacaoEmAndamento =
            true;


        chaveEmValidacao =
            snapshot.chave;


        const temporizadorApi =
            setTimeout(
                () => {

                    controlador.abort();
                },

                TEMPO_LIMITE_API_MS
            );


        try {

            /*
             * Validação matemática local.
             */

            if (
                snapshot.cpf &&

                !validarCpfLocal(
                    snapshot.cpf
                )
            ) {

                const resultadoInvalido = {

                    allowed: false,

                    code:
                        "INVALID_CPF",

                    message:
                        "Informe um CPF válido para continuar a compra.",
                };


                ultimaChaveValidada =
                    snapshot.chave;


                ultimoResultado =
                    resultadoInvalido;


                aplicarResultado(
                    resultadoInvalido
                );


                return;
            }


            /*
             * Sem sessão/loja identificável,
             * NÃO libera.
             */

            if (
                !snapshot.storeId ||
                !snapshot.sessionId
            ) {

                throw new ErroSegurancaCheckout(

                    401,

                    "Sessão do checkout ainda não está disponível."
                );
            }


            /*
             * Token temporário.
             */

            const token =
                await obterTokenCheckout(

                    snapshot,

                    controlador.signal
                );


            /*
             * Validação no backend.
             */

            const resposta =
                await fetch(
                    API_URL,
                    {

                        method: "POST",

                        headers: {

                            "Content-Type":
                                "application/json",

                            "X-Store-ID":
                                snapshot.storeId,

                            "X-Checkout-Session":
                                snapshot.sessionId,

                            "X-Checkout-Token":
                                token,
                        },

                        body:
                            JSON.stringify({

                                cpf:
                                    snapshot.cpf,

                                items:
                                    snapshot.itens,
                            }),

                        signal:
                            controlador.signal,
                    }
                );


            const resultado =
                await resposta
                    .json()
                    .catch(
                        () => ({})
                    );


            /*
             * Qualquer HTTP diferente de sucesso
             * mantém bloqueado.
             */

            if (!resposta.ok) {

                /*
                 * Erro relacionado a autenticação,
                 * rate limit ou segurança.
                 */

                if (
                    (
                        resposta.status >= 400 &&
                        resposta.status < 500
                    ) ||

                    resposta.status === 503
                ) {

                    checkoutToken = "";

                    checkoutTokenExpiraEmMs = 0;


                    throw new ErroSegurancaCheckout(

                        resposta.status,

                        resultado.message ||

                        "A validação de segurança recusou a solicitação."
                    );
                }


                /*
                 * Inclusive erro 500 NÃO libera.
                 */

                throw new Error(

                    `Erro HTTP ${resposta.status}`
                );
            }


            /*
             * Se outra validação começou enquanto
             * esta estava aguardando, esta resposta
             * virou obsoleta.
             *
             * NUNCA pode liberar o estado novo.
             */

            if (
                numeroValidacao !==
                contadorValidacao
            ) {

                return;
            }


            ultimaChaveValidada =
                snapshot.chave;


            ultimoResultado =
                resultado;


            aplicarResultado(
                resultado
            );


            console.log(

                "[Bloqueio CPF] Validação:",

                resultado.code ??
                "SEM_CODIGO"
            );

        }

        catch (erro) {

            /*
             * Resultado antigo.
             */

            if (
                numeroValidacao !==
                contadorValidacao
            ) {

                return;
            }


            let resultadoBloqueado;


            /*
             * Falha na camada de segurança.
             */

            if (
                erro instanceof
                ErroSegurancaCheckout
            ) {

                console.warn(

                    "[Bloqueio CPF] Requisição recusada pela camada de segurança:",

                    erro.status
                );


                resultadoBloqueado = {

                    allowed: false,

                    code:
                        "VALIDATION_SECURITY_BLOCKED",

                    message:
                        erro.status === 429

                            ?

                            "Muitas tentativas de validação. Aguarde alguns instantes."

                            :

                            MENSAGEM_INDISPONIVEL,
                };
            }

            else {

                /*
                 * Timeout.
                 */

                if (
                    erro instanceof
                    DOMException &&

                    erro.name ===
                    "AbortError"
                ) {

                    console.warn(

                        "[Bloqueio CPF] Validação cancelada ou expirada."
                    );
                }

                else {

                    console.error(

                        "[Bloqueio CPF] Erro ao consultar API:",

                        erro
                    );
                }


                /*
                 * =====================================
                 * FAIL-CLOSED
                 * =====================================
                 *
                 * IMPORTANTE:
                 *
                 * Nunca colocar:
                 *
                 * allowed: true
                 *
                 * aqui.
                 *
                 * Falha de rede/Render/API deve
                 * manter o checkout bloqueado.
                 */

                resultadoBloqueado = {

                    allowed: false,

                    code:
                        "VALIDATION_UNAVAILABLE_BLOCKED",

                    message:
                        MENSAGEM_INDISPONIVEL,
                };
            }


            ultimaChaveValidada =
                snapshot.chave;


            ultimoResultado =
                resultadoBloqueado;


            aplicarResultado(
                resultadoBloqueado
            );
        }

        finally {

            clearTimeout(
                temporizadorApi
            );


            if (
                numeroValidacao ===
                contadorValidacao
            ) {

                validacaoEmAndamento =
                    false;


                chaveEmValidacao =
                    "";


                controladorAtual =
                    null;
            }
        }
    }


    /*
     * ------------------------------------------------
     * AGENDAMENTO
     * ------------------------------------------------
     */

    function agendarValidacao(

        forcarConsulta = false,

        atraso =
            ATRASO_VALIDACAO_MS

    ) {

        if (
            temporizadorValidacao !==
            null
        ) {

            clearTimeout(
                temporizadorValidacao
            );
        }


        temporizadorValidacao =
            setTimeout(
                () => {

                    temporizadorValidacao =
                        null;


                    void validarCheckout(
                        forcarConsulta
                    );
                },

                atraso
            );
    }


    /*
     * O detalhe mais importante desta versão:
     *
     * primeiro bloqueia;
     * depois agenda a API.
     *
     * Portanto o debounce NÃO cria janela
     * para finalizar compra.
     */

    function bloquearEAgendar(

        forcarConsulta = false,

        atraso =
            ATRASO_VALIDACAO_MS

    ) {

        bloquearDuranteValidacao();

        agendarValidacao(
            forcarConsulta,
            atraso
        );
    }


    /*
     * ------------------------------------------------
     * RECONSTRUÇÃO DO CHECKOUT
     * ------------------------------------------------
     */

    function tratarReconstrucaoDoCheckout(

        forcarConsulta = true

    ) {

        /*
         * PRIMEIRO BLOQUEIA.
         */

        bloquearDuranteValidacao();


        /*
         * DEPOIS consulta.
         */

        agendarValidacao(
            forcarConsulta
        );


        /*
         * O checkout pode reconstruir componentes
         * depois do evento.
         *
         * Reaplica o bloqueio algumas vezes.
         */

        setTimeout(
            () => {

                if (
                    checkoutBloqueado
                ) {

                    reaplicarBloqueioAtual();
                }
            },

            50
        );


        setTimeout(
            () => {

                if (
                    checkoutBloqueado
                ) {

                    reaplicarBloqueioAtual();
                }
            },

            250
        );


        setTimeout(
            () => {

                if (
                    checkoutBloqueado
                ) {

                    reaplicarBloqueioAtual();
                }
            },

            500
        );
    }


    /*
     * =================================================
     * EVENTOS
     * =================================================
     *
     * Todos bloqueiam ANTES da nova validação.
     */


    nube.on(
        "checkout:ready",
        () => {

            tratarReconstrucaoDoCheckout(
                true
            );
        }
    );


    nube.on(
        "page:loaded",
        () => {

            tratarReconstrucaoDoCheckout(
                true
            );
        }
    );


    nube.on(
        "cart:update",
        () => {

            bloquearEAgendar(

                false,

                ATRASO_VALIDACAO_MS
            );
        }
    );


    nube.on(
        "customer:update",
        () => {

            /*
             * Bloqueia AGORA.
             *
             * A API pode esperar 120ms,
             * o botão não.
             */

            bloquearEAgendar(
                false,
                120
            );
        }
    );


    nube.on(
        "shipping:update",
        () => {

            tratarReconstrucaoDoCheckout(
                true
            );
        }
    );


    nube.on(
        "payment:update",
        () => {

            tratarReconstrucaoDoCheckout(
                true
            );
        }
    );


    nube.on(
        "location:updated",
        () => {

            /*
             * Mudança de localização/página:
             * volta imediatamente para FAIL.
             */

            bloquearEAgendar(
                false,
                0
            );
        }
    );


    /*
     * =================================================
     * WATCHDOG
     * =================================================
     *
     * Enquanto o backend não responder
     * allowed === true, o checkout permanece
     * sendo reafirmado como inválido.
     *
     * Isto NÃO chama sua API.
     */

    setInterval(
        () => {

            if (
                checkoutBloqueado
            ) {

                reaplicarBloqueioAtual();
            }
        },

        INTERVALO_REAPLICACAO_MS
    );


    /*
     * =================================================
     * PRIMEIRA VALIDAÇÃO
     * =================================================
     *
     * Neste ponto o checkout JÁ ESTÁ BLOQUEADO.
     *
     * Agora apenas iniciamos a chamada de validação.
     */

    agendarValidacao(
        true,
        0
    );
}