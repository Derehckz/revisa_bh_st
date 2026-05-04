import { expect, test } from "@playwright/test";

test("app shell renders and routes are reachable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Boletas SaaS")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await page.getByRole("link", { name: "Período" }).click();
  await expect(page.getByRole("heading", { name: "Vista de período" })).toBeVisible();

  await page.getByRole("link", { name: "Boletas" }).click();
  await expect(page.getByRole("heading", { name: "Tabla de boletas" })).toBeVisible();

  await page.getByRole("link", { name: "Runs" }).click();
  await expect(page.getByRole("heading", { name: "Runs y auditoría" })).toBeVisible();

  await page.getByRole("link", { name: "Configuración" }).click();
  await expect(page.getByRole("heading", { name: "Configuración" })).toBeVisible();
});

test("keyboard shortcuts do not crash UI", async ({ page }) => {
  await page.goto("/boletas");
  await expect(page.getByRole("heading", { name: "Tabla de boletas" })).toBeVisible();

  await page.keyboard.press("Control+b");
  await page.keyboard.press("/");
  await page.keyboard.type("test");
  await page.keyboard.press("Escape");

  await expect(page.getByRole("heading", { name: "Tabla de boletas" })).toBeVisible();
});
