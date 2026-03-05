we should supply with a good default set of tags and entity categories

tags:
```json
{
  "tags": [
    {"name": "housing", "type": "expense", "description": "Rent, mortgage payments, condo/HOA fees, and other core housing payments."},
    {"name": "home_maintenance", "type": "expense", "description": "Home repairs, contractors, renovations, and maintenance services."},
    {"name": "utilities", "type": "expense", "description": "Electricity, gas, water, trash, heating, and other utility bills."},
    {"name": "internet_mobile", "type": "expense", "description": "Internet service, mobile phone plans, and related connectivity charges."},

    {"name": "grocery", "type": "expense", "description": "Food and household staples from grocery stores and supermarkets."},
    {"name": "dining_out", "type": "expense", "description": "Restaurants, takeout, delivery, and prepared meals purchased to eat."},
    {"name": "coffee_snacks", "type": "expense", "description": "Coffee shops, bubble tea, desserts, snacks, and small convenience food purchases."},
    {"name": "alcohol_bars", "type": "expense", "description": "Bars, pubs, alcohol purchases, and related nightlife spending."},

    {"name": "shopping", "type": "expense", "description": "General retail and online purchases that do not fit a more specific category."},
    {"name": "clothing", "type": "expense", "description": "Clothing, shoes, accessories, and related apparel purchases."},
    {"name": "electronics", "type": "expense", "description": "Electronics, gadgets, computers, phones, and related accessories."},
    {"name": "home", "type": "expense", "description": "Furniture, decor, household supplies, and other home-related purchases (excluding maintenance/repairs and core housing payments)."},

    {"name": "personal_care", "type": "expense", "description": "Haircuts, grooming, cosmetics, toiletries, and personal care services."},
    {"name": "health_medical", "type": "expense", "description": "Doctor visits, dental, vision, clinics, tests, and other medical services."},
    {"name": "pharmacy", "type": "expense", "description": "Prescriptions and over-the-counter medication purchases at pharmacies."},
    {"name": "fitness", "type": "expense", "description": "Gym memberships, fitness classes, sports training, and fitness-related spending."},

    {"name": "transportation", "type": "expense", "description": "Public transit, rideshare, taxis, and other non-car transportation."},
    {"name": "fuel", "type": "expense", "description": "Gasoline, diesel, EV charging, and other vehicle energy costs."},
    {"name": "auto", "type": "expense", "description": "Car maintenance, repairs, parking, tolls, registration, and car-related costs excluding fuel and insurance."},

    {"name": "insurance", "type": "expense", "description": "Insurance premiums such as home, auto, life, travel, or other policies."},
    {"name": "travel", "type": "expense", "description": "Flights, hotels, bookings, and other trip-related spending."},
    {"name": "entertainment", "type": "expense", "description": "Movies, events, tickets, hobbies, and leisure activities."},
    {"name": "subscriptions", "type": "expense", "description": "Recurring subscriptions like streaming, software, apps, and memberships."},
    {"name": "education", "type": "expense", "description": "Tuition, courses, training, books, and education-related expenses."},
    {"name": "gifts", "type": "expense", "description": "Gifts given to others, including holidays and special occasions."},
    {"name": "donations_charity", "type": "expense", "description": "Charitable donations and other non-profit contributions."},
    {"name": "kids_childcare", "type": "expense", "description": "Childcare, kids activities, school-related costs, and child expenses."},
    {"name": "pets", "type": "expense", "description": "Pet food, vet visits, grooming, supplies, and pet services."},

    {"name": "taxes", "type": "expense", "description": "Income tax payments, property tax, installments, and other taxes paid."},
    {"name": "fees", "type": "expense", "description": "Bank fees, service charges, penalties, and miscellaneous fees."},
    {"name": "interest_expense", "type": "expense", "description": "Interest paid on credit cards, loans, lines of credit, or financing."},

    {"name": "salary_wages", "type": "income", "description": "Regular salary, wages, and payroll income."},
    {"name": "bonus", "type": "income", "description": "Bonuses, commissions, and other variable compensation."},
    {"name": "business_income", "type": "income", "description": "Self-employment, freelance, contract, or business revenue."},
    {"name": "interest_income", "type": "income", "description": "Interest earned from bank accounts, GICs, bonds, or lending."},
    {"name": "dividends", "type": "income", "description": "Dividend income from stocks, funds, or other investments."},
    {"name": "investment_gains", "type": "income", "description": "Realized gains from selling investments or assets."},
    {"name": "refund", "type": "income", "description": "Refunds for prior purchases, returns, chargebacks, or reimbursements treated as income."},
    {"name": "reimbursement", "type": "income", "description": "Repayments for expenses you covered (work, shared purchases, reimbursements)."},
    {"name": "gifts_received", "type": "income", "description": "Money received as gifts from others."},
    {"name": "other_income", "type": "income", "description": "Any income that does not fit the other income categories."},

    {
      "name": "internal_transfer",
      "type": "internal",
      "description": "Money moved between your own accounts (e.g., chequing to savings, paying your own credit card from chequing). Not income or expense."
    },
    {
      "name": "e_transfer",
      "type": "internal",
      "description": "Interac e-Transfer payment method marker (send/receive). Use alongside a purpose tag when known, or with needs_review when unknown."
    },
    {
      "name": "needs_review",
      "type": "internal",
      "description": "Purpose is unclear or classification is uncertain and needs manual follow-up."
    },
    {"name": "cash_withdrawal", "type": "internal", "description": "ATM and cash withdrawals used to obtain physical cash."},
    {"name": "debt_payment", "type": "internal", "description": "Payments toward credit cards, loans, or other debt principal/settlement movements."},
    {"name": "savings_investments", "type": "internal", "description": "Contributions or deposits into savings or investment accounts (movement, not spending)."},
    {"name": "uncategorized", "type": "internal", "description": "Fallback tag for transactions not yet classified."},
    {"name": "one_time", "type": "internal", "description": "Marks a transaction as irregular/non-recurring for reporting and budgeting."},
    {"name": "needs_review", "type": "internal", "description": "Marks a transaction that needs confirmation or manual cleanup."}
  ]
}
```

entity categories:
```json
{
  "entity_categories": [
    {
      "name": "merchant",
      "description": "Default for businesses the user buys from (retail, restaurants, apps, online services, marketplaces, rideshare, etc.)"
    },
    {
      "name": "account",
      "description": "A specific account/instrument the user owns or manages (checking, credit card, prepaid card, transit card, loan). Use when the entity represents the account itself, not the bank."
    },
    {
      "name": "financial_institution",
      "description": "Banks, credit unions, brokerages, payment processors, card issuers (the institution, not the user's specific account)."
    },
    {
      "name": "government",
      "description": "Government bodies and agencies (tax authority, city/province/federal departments)."
    },
    {
      "name": "utility_provider",
      "description": "Providers of utilities and essential services (electricity, gas, water, telecom, internet)."
    },
    {
      "name": "employer",
      "description": "Organizations that pay the user compensation (salary, wages)."
    },
    {
      "name": "investment_entity",
      "description": "Investment counterparties not well-modeled as a merchant (funds, VC/PE firms, investment partnerships)."
    },
    {
      "name": "person",
      "description": "Individuals (friends/family/roommates) when the user wants a named counterparty."
    },
    {
      "name": "placeholder",
      "description": "Temporary/unknown entity used during ingestion or when the counterparty is unclear."
    },
    {
      "name": "organization",
      "description": "Catch-all for non-merchant orgs that aren’t clearly government/financial/utility/employer (e.g., nonprofits, clubs, associations)."
    }
  ]
}
```

let's reset the current local db (remove everything, except for the two accounts), and seed the tags and entity categories.

for benchmark, the default snapshot would be an empty db with the two accounts, and these tags and entity categories.