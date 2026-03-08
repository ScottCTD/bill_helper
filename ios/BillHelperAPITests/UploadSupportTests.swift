import XCTest
@testable import BillHelperApp

final class UploadSupportTests: XCTestCase {
    func testAgentMessageMultipartEncodesContentAndFiles() throws {
        let attachment = try AttachmentUpload(
            filename: "receipt.pdf",
            mimeType: "application/pdf",
            data: Data("file-data".utf8)
        )

        let multipart = MultipartFormDataBuilder.agentMessage(
            content: "Please review this invoice.",
            attachments: [attachment],
            boundary: "boundary-123"
        )

        let body = String(decoding: multipart.body, as: UTF8.self)
        XCTAssertEqual(multipart.contentType, "multipart/form-data; boundary=boundary-123")
        XCTAssertTrue(body.contains("name=\"content\""))
        XCTAssertTrue(body.contains("Please review this invoice."))
        XCTAssertTrue(body.contains("filename=\"receipt.pdf\""))
        XCTAssertTrue(body.contains("Content-Type: application/pdf"))
    }

    func testAttachmentRejectsUnsupportedMimeTypes() {
        XCTAssertThrowsError(
            try AttachmentUpload(filename: "notes.txt", mimeType: "text/plain", data: Data())
        ) { error in
            XCTAssertEqual(error as? AttachmentUploadError, .unsupportedMimeType("text/plain"))
        }
    }
}