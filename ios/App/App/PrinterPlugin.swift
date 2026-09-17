import Foundation
import Capacitor
import UIKit
import AVFoundation

/// WebView 안에 그려 둔 인쇄 조판을 iOS 인쇄(또는 PDF 저장·공유)로 넘긴다.
/// 웹의 window.print() 는 WKWebView 에서 아무 일도 하지 않는다.
@objc(PrinterPlugin)
public class PrinterPlugin: CAPPlugin, CAPBridgedPlugin {
  public let identifier = "PrinterPlugin"
  public let jsName = "Printer"
  public let pluginMethods: [CAPPluginMethod] = [
    CAPPluginMethod(name: "print", returnType: CAPPluginReturnPromise),
    CAPPluginMethod(name: "audioFocus", returnType: CAPPluginReturnPromise)
  ]

  /// 우리 미디어를 틀 때(on) 오디오 세션을 잡아 다른 앱 음악을 멈추고, 끝나면(off) 돌려준다
  @objc func audioFocus(_ call: CAPPluginCall) {
    let on = call.getBool("on") ?? true
    do {
      let s = AVAudioSession.sharedInstance()
      if on {
        try s.setCategory(.playback, mode: .default, options: [])
        try s.setActive(true)
      } else {
        try s.setActive(false, options: [.notifyOthersOnDeactivation])
        try s.setCategory(.playback, mode: .default, options: [.mixWithOthers])
      }
      call.resolve()
    } catch { call.reject(error.localizedDescription) }
  }

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
