Few improvements to the dashboard:

Overview tab:
1. The Income vs Expense Trend plot should be displayed above the "view" control bar. This is because that plot is date-agnostic as it's like an overview. The segment order should be "day-to-day", "fixed", "one-time", "transfers", "untagged". Also, I expect that when I hover over the segment, the tooltip should ONLY show the amount of the segment. Now hovering will show all 5 filter groups' amounts which are distracting.
3. Replace the "Expense by Filter Group" pie chart with a Sankey plot which would show the flow of total expense to different filter groups. For builtin filter groups, always order them in "day-to-day", "fixed", "one-time", "transfers", "untagged". No custom groups should be shown in the Sankey plot. Then, the Sankey plot should extend another level to show the details of each filter group. Color each flow correspondingly, and add tooltips to each filter group and tags.

Spending tab:

1. The "Daily Spending by Filter Group" should only show the trend of the "day-to-day" filter group. Don't use a line plot, use a bar plot instead to show exactly the bar of each day.
2. In the "Spending" tab, also add a table, below the "day-to-day" bar plot, which would show the monthly spend by filter group, including custom filter groups. Table header: "Filter Group", "Monthly Spend", "Delta to Last Month". The delta should be shown as both a raw amount, and a percentage, colored by positive or negative.
3. The "Average spend day" should be "Average Daily Spend (Day-to-Day)" which should be the average of the "day-to-day" filter group. Similar for the median.

