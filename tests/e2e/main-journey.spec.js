const { test, expect } = require("@playwright/test");

async function mockApi(page) {
  await page.route("**/api/auth/registrar", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        usuario: {
          id: "user-e2e",
          nome: "Lua Teste",
          email: "lua.teste@example.com",
          role: "cliente",
          credits_balance: 100
        },
        expires_in: 86400
      })
    });
  });

  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        usuario: {
          id: "user-e2e",
          nome: "Lua Teste",
          email: "lua.teste@example.com",
          role: "cliente",
          credits_balance: 100
        },
        expires_in: 86400
      })
    });
  });

  await page.route("**/api/me/credits", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ credits_balance: 100 })
    });
  });

  await page.route("**/api/carta-do-dia", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        carta: "A Sacerdotisa",
        simbolo: "☽",
        mensagem: "Escute sua intuicao antes de agir."
      })
    });
  });

  await page.route("**/api/leitura", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        question_id: "q-e2e",
        reading_id: "r-e2e",
        interpretacao: "As cartas mostram clareza, prudencia e um proximo passo objetivo.",
        cartas: [
          { nome: "O Mago", invertida: false, simbolo: "✦" },
          { nome: "A Sacerdotisa", invertida: false, simbolo: "☽" },
          { nome: "O Sol", invertida: false, simbolo: "☀" }
        ]
      })
    });
  });

  await page.route("**/api/offers/after-reading", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        upsell: {
          ritual_id: "ritual-lua",
          nome: "Ritual de Clareza",
          descricao: "Um proximo passo guiado para organizar sua decisao."
        }
      })
    });
  });

  await page.route("**/api/checkout", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        payment_id: "pay-e2e",
        url: "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=e2e"
      })
    });
  });
}

test.describe("jornada principal", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
  });

  test("cadastro, carta do dia, leitura e pagamento", async ({ page }) => {
    await page.getByRole("link", { name: /comecar consulta/i }).click();
    await page.locator("#tabCadastro").click();

    await page.locator("#cadNome").fill("Lua Teste");
    await page.locator("#cadEmail").fill("lua.teste@example.com");
    await page.locator("#cadSenha").fill("senha123");
    await page.locator("#cadLegalAccept").check();
    await page.locator("#formCadastroEl").getByRole("button", { name: /criar minha conta/i }).click();

    await expect(page.locator("#consultaArea")).toBeVisible();
    await expect(page.locator("#perguntaInput")).toBeFocused();

    await page.locator("#cartaDoDia").dispatchEvent("click");
    await expect(page.locator("#cardName")).toContainText("A Sacerdotisa");

    await page.locator("#perguntaInput").fill("Qual o proximo passo para minha carreira?");
    await page.locator("#btnConsultar").click();

    await expect(page.locator("#resultadoCartas")).toBeVisible();
    await expect(page.locator("#resultadoTexto")).toContainText("proximo passo objetivo");
    await expect(page.locator("#ritualOfferAfterReading")).toContainText("Ritual de Clareza");

    await page.locator("#planos").scrollIntoViewIfNeeded();
    const [request] = await Promise.all([
      page.waitForRequest("**/api/checkout"),
      page.locator(".pricing2-button").first().click()
    ]);
    expect(request.method()).toBe("POST");
  });

  test("login e erro de leitura amigavel", async ({ page }) => {
    await page.getByRole("link", { name: /entrar/i }).first().click();
    await page.locator("#loginEmail").fill("lua.teste@example.com");
    await page.locator("#loginSenha").fill("senha123");
    await page.locator("#formLoginEl").getByRole("button", { name: /entrar no portal/i }).click();

    await page.route("**/api/leitura", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Servico temporariamente indisponivel." })
      });
    });

    await page.locator("#perguntaInput").fill("O que preciso observar hoje?");
    await page.locator("#btnConsultar").click();

    await expect(page.locator("#resultadoApiError")).toBeVisible();
    await expect(page.locator("#resultadoApiErrorText")).toContainText("indisponivel");
  });
});
