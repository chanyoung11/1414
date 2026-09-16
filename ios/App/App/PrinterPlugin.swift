import Foundation
import Capacitor
import UIKit

/// WebView 안에 그려 둔 인쇄 조판을 iOS 인쇄(또는 PDF 저장·공유)로 넘긴다.
/// 웹의 window.print() 는 WKWebView 에서 아무 일도 하지 않는다.
@objc(PrinterPlugin)
public class PrinterPlugin: CAPPlugin, CAPBridgedPlugin {
  public let identifier = "PrinterPlugin"
  public let jsName = "Printer"
  public let pluginMethods: [CAPPluginMethod] = [
    CAPPluginMethod(name: "print", returnType: CAPPluginReturnPromise)
  ]

  @objc func print(_ call: CAPPluginCall) {
    DispatchQueue.main.async {
      guard let webView = self.bridge?.webView else {
        call.reject("화면을 찾지 못했어요"); return
      }
      let info = UIPrintInfo(dictionary: nil)
      info.outputType = .general
      info.jobName = call.getString("name") ?? "1414"
      let controller = UIPrintInteractionController.shared
      controller.printInfo = info
      controller.printFormatter = webView.viewPrintFormatter()
      controller.present(animated: true) { (_, completed, error) in
        if let error = error { call.reject(error.localizedDescription) }
        else { call.resolve(["completed": completed]) }
      }
    }
  }
}
