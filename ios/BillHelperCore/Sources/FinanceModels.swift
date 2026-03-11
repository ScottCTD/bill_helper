import Foundation

enum FinanceFormatters {
    static let isoDayIn = "yyyy-MM-dd"
    static let isoTimestampIn = "yyyy-MM-dd'T'HH:mm:ss"

    static let monthFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "MMM yyyy"
        return formatter
    }()

    static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "MMM d"
        return formatter
    }()

    static let dayInputFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = isoDayIn
        return formatter
    }()

    static func monthLabel(for monthKey: String) -> String {
        guard
            let monthDate = dayInputFormatter.date(from: "\(monthKey)-01")
        else {
            return monthKey
        }
        return monthFormatter.string(from: monthDate)
    }

    static func dayLabel(for rawValue: String) -> String {
        if let date = dayInputFormatter.date(from: rawValue) {
            return dayFormatter.string(from: date)
        }
        if let date = ISO8601DateFormatter().date(from: rawValue) {
            return dayFormatter.string(from: date)
        }
        return rawValue
    }

    static func relativeTimestamp(for rawValue: String, relativeTo now: Date = .now) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        if let date = ISO8601DateFormatter().date(from: rawValue) {
            return formatter.localizedString(for: date, relativeTo: now)
        }
        return rawValue
    }

    static func currency(_ amountMinor: Int, currencyCode: String) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = currencyCode
        formatter.maximumFractionDigits = 2
        formatter.minimumFractionDigits = 2
        let major = Decimal(amountMinor) / 100
        return formatter.string(from: NSDecimalNumber(decimal: major)) ?? "\(currencyCode) \(major)"
    }

    static func signedCurrency(_ amountMinor: Int, currencyCode: String) -> String {
        let prefix = amountMinor > 0 ? "+" : amountMinor < 0 ? "-" : ""
        return prefix + currency(abs(amountMinor), currencyCode: currencyCode)
    }
}
