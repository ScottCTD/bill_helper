import { expect, test, type Page } from "@playwright/test";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

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

function currentSessionUserLabel(page: Page, userName: string) {
  return page.getByText(new RegExp(`^${escapeRegExp(userName)}$`));
}

function adminUserRow(page: Page, userName: string) {
  return page.locator("tr").filter({
    has: page.getByRole("textbox", {
      name: new RegExp(`^${escapeRegExp(userName)} display name$`, "i"),
    }),
  }).first();
}

test.describe("admin auth flows", () => {
  test("signed in admin sees current identity and admin navigation", async ({ page }) => {
    await signIn(page, "admin", "admin-password");
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("link", { name: "Admin" })).toBeVisible();
    await expect(currentSessionUserLabel(page, "admin")).toBeVisible();
  });

  test("admin can reset a user's password and the user can sign back in", async ({ page }) => {
    const suffix = Date.now();
    const username = `pw-reset-${suffix}`;
    const originalPassword = `pw-start-${suffix}`;
    const nextPassword = `pw-next-${suffix}`;

    await signIn(page, "admin", "admin-password");
    await page.getByRole("link", { name: "Admin" }).click();
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();

    await page.getByLabel("New user name").fill(username);
    await page.getByLabel("New user password").fill(originalPassword);
    await page.getByRole("button", { name: "Create user" }).click();

    const userRow = adminUserRow(page, username);
    await expect(userRow).toBeVisible();

    const resetPasswordField = userRow.getByLabel(`Reset password for ${username}`);
    await resetPasswordField.fill(nextPassword);
    await userRow.getByRole("button", { name: "Reset password" }).click();
    await expect(resetPasswordField).toHaveValue("");

    await signOut(page);

    await signIn(page, username, originalPassword);
    await expect(page.getByText("Invalid username or password.")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);

    await signIn(page, username, nextPassword);
    await expect(page).toHaveURL("/");
    await expect(currentSessionUserLabel(page, username)).toBeVisible();
  });
});
