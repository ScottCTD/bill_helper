import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, username: string, password: string) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("User name").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

test.describe("session auth", () => {
  test("admin can create a user, impersonate them, and create an owned account", async ({ page }) => {
    const suffix = Date.now();
    const username = `pw-user-${suffix}`;
    const password = `pw-pass-${suffix}`;
    const accountName = `pw-account-${suffix}`;

    await signIn(page, "admin", "admin-password");
    await expect(page).toHaveURL("/");
    await expect(page.getByText("admin (admin)")).toBeVisible();

    await page.getByRole("link", { name: "Admin" }).click();
    await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();

    await page.getByLabel("New user name").fill(username);
    await page.getByLabel("New user password").fill(password);
    await page.getByRole("button", { name: "Create user" }).click();

    const userRow = page.locator("tr").filter({ has: page.locator(`input[value="${username}"]`) }).first();
    await expect(userRow).toBeVisible();
    await userRow.getByRole("button", { name: "Log in as" }).click();

    await expect(page.getByText(`Impersonating ${username}.`)).toBeVisible();
    await expect(page.getByText(`${username} (impersonating)`)).toBeVisible();
    await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);

    await page.getByRole("link", { name: "Accounts" }).click();
    await expect(page.getByRole("heading", { name: "Accounts" })).toBeVisible();
    await page.getByRole("button", { name: "Create account" }).click();

    const createDialog = page.getByRole("dialog");
    await expect(createDialog.getByRole("heading", { name: "Create Account" })).toBeVisible();
    await createDialog.getByLabel("Name").fill(accountName);
    await createDialog.getByRole("button", { name: "Create account" }).click();

    const accountRow = page.locator("tr").filter({ hasText: accountName }).first();
    await expect(accountRow).toContainText(accountName);
    await expect(accountRow).toContainText(username);

    await signOut(page);
    await signIn(page, "admin", "admin-password");
    await page.getByRole("link", { name: "Accounts" }).click();
    await page.getByLabel("Search").fill(accountName);
    await expect(page.locator("tr").filter({ hasText: accountName }).first()).toContainText(username);
  });

  test("user can rotate their password from settings and sign back in", async ({ page }) => {
    const suffix = Date.now();
    const username = `pw-settings-${suffix}`;
    const originalPassword = `pw-start-${suffix}`;
    const nextPassword = `pw-next-${suffix}`;

    await signIn(page, "admin", "admin-password");
    await page.getByRole("link", { name: "Admin" }).click();

    await page.getByLabel("New user name").fill(username);
    await page.getByLabel("New user password").fill(originalPassword);
    await page.getByRole("button", { name: "Create user" }).click();
    await expect(page.locator("tr").filter({ has: page.locator(`input[value="${username}"]`) }).first()).toBeVisible();

    await signOut(page);
    await signIn(page, username, originalPassword);

    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    await page.getByLabel(/^Current password$/).fill(originalPassword);
    await page.getByLabel(/^New password$/).fill(nextPassword);
    await page.getByLabel(/^Confirm new password$/).fill(nextPassword);
    await page.getByRole("button", { name: "Change password" }).click();
    await expect(page.getByLabel(/^Current password$/)).toHaveValue("");
    await expect(page.getByLabel(/^New password$/)).toHaveValue("");
    await expect(page.getByLabel(/^Confirm new password$/)).toHaveValue("");

    await signOut(page);
    await signIn(page, username, nextPassword);
    await expect(page.getByText(username)).toBeVisible();
  });
});
