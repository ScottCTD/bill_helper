import Foundation

enum AttachmentUploadError: LocalizedError, Equatable {
    case unsupportedMimeType(String)

    var errorDescription: String? {
        switch self {
        case .unsupportedMimeType(let mimeType):
            return "Unsupported attachment MIME type: \(mimeType)"
        }
    }
}

struct AttachmentUpload: Equatable {
    let filename: String
    let mimeType: String
    let data: Data

    init(filename: String, mimeType: String, data: Data) throws {
        guard Self.isSupported(mimeType: mimeType) else {
            throw AttachmentUploadError.unsupportedMimeType(mimeType)
        }
        self.filename = filename
        self.mimeType = mimeType
        self.data = data
    }

    private static func isSupported(mimeType: String) -> Bool {
        mimeType == "application/pdf" || mimeType.lowercased().hasPrefix("image/")
    }
}

struct MultipartFormData: Equatable {
    let body: Data
    let contentType: String
}

enum MultipartFormDataBuilder {
    static func agentMessage(
        content: String,
        attachments: [AttachmentUpload],
        boundary: String = UUID().uuidString
    ) -> MultipartFormData {
        var data = Data()
        data.appendUTF8("--\(boundary)\r\n")
        data.appendUTF8("Content-Disposition: form-data; name=\"content\"\r\n\r\n")
        data.appendUTF8(content)
        data.appendUTF8("\r\n")

        for attachment in attachments {
            data.appendUTF8("--\(boundary)\r\n")
            data.appendUTF8(
                "Content-Disposition: form-data; name=\"files\"; filename=\"\(attachment.filename)\"\r\n"
            )
            data.appendUTF8("Content-Type: \(attachment.mimeType)\r\n\r\n")
            data.append(attachment.data)
            data.appendUTF8("\r\n")
        }

        data.appendUTF8("--\(boundary)--\r\n")
        return MultipartFormData(body: data, contentType: "multipart/form-data; boundary=\(boundary)")
    }
}

private extension Data {
    mutating func appendUTF8(_ string: String) {
        append(contentsOf: string.utf8)
    }
}