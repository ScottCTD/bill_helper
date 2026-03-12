import { expect, test, type Page } from "@playwright/test";

const adminCredentials = {
  username: "admin",
  password: "admin-password",
} as const;

const aliceCredentials = {
  username: "alice",
  password: "alice-password",
} as const;

const bobCredentials = {
  username: "bob",
  password: "bob-password",
} as const;

const aliceAccountName = "Alice Checking";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function signInAtProtectedRoute(
  page: Page,
  path: string,
  credentials: { username: string; password: string },
) {
  await page.goto(path);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("User name").fill(credentials.username);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

function adminUserRow(page: Page, userName: string) {
  return page.locator("tr").filter({
    has: page.getByRole("textbox", {
      name: new RegExp(`^${escapeRegExp(userName)} display name$`, "i"),
    }),
  });
}

async function createUser(
  page: Page,
  credentials: { username: string; password: string },
) {
  await page.getByPlaceholder("e.g. alice").fill(credentials.username);
  await page
    .getByPlaceholder("Set an initial password")
    .fill(credentials.password);
  await page.getByRole("button", { name: "Create user" }).click();
  await expect(adminUserRow(page, credentials.username)).toHaveCount(1);
}

async function createAccount(page: Page, accountName: string) {
  await page.goto("/accounts");
  const createAccountButton = page.getByRole("button", { name: "Create account" });
  await expect(createAccountButton).toBeVisible();
  await createAccountButton.click();

  const createDialog = page.getByRole("dialog", { name: "Create Account" });
  await expect(createDialog).toBeVisible();
  await createDialog.getByLabel("Name").fill(accountName);
  await createDialog.getByRole("button", { name: "Create account" }).click();

  await expect(page.locator("tr").filter({ hasText: accountName }).first()).toBeVisible();
}

test("rejects invalid password login", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("User name").fill(adminCredentials.username);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(
    page.getByText("Invalid username or password."),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("supports admin user creation, impersonation, and owner-scoped account visibility", async ({
  page,
}) => {
  await signInAtProtectedRoute(page, "/admin", adminCredentials);
  await expect(page).toHaveURL(/\/admin$/);
  await expect(
    page.getByRole("heading", { level: 3, name: "Admin" }),
  ).toBeVisible();

  await createUser(page, aliceCredentials);
  await createUser(page, bobCredentials);

  const aliceRow = adminUserRow(page, aliceCredentials.username);
  await aliceRow.getByRole("button", { name: "Log in as" }).click();
  await expect(
    page.getByText(/^Impersonating alice\. Log out when you want to end this session\.$/),
  ).toBeVisible();

  await createAccount(page, aliceAccountName);
  await expect(
    page.getByText(/^Impersonating alice\. Log out when you want to end this session\.$/),
  ).toBeVisible();

  await signOut(page);

  await signInAtProtectedRoute(page, "/accounts", aliceCredentials);
  await expect(page).toHaveURL(/\/accounts$/);
  await expect(page.locator("tr").filter({ hasText: aliceAccountName }).first()).toBeVisible();

  await signOut(page);

  await signInAtProtectedRoute(page, "/accounts", bobCredentials);
  await expect(page).toHaveURL(/\/accounts$/);
  await expect(page.getByText("No accounts yet.")).toBeVisible();
  await expect(page.locator("tr").filter({ hasText: aliceAccountName })).toHaveCount(0);
});
