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
    CAPPluginMethod(name: "audioFocus", returnType: CAPPluginReturnPromise),
    CAPPluginMethod(name: "saveFile", returnType: CAPPluginReturnPromise)
  ]

  /// 파일 내보내기(콘티 파일·MusicXML). 웹뷰의 <a download> 는 아무 일도 하지 않아서, 웹이 만든 글을
  /// 임시 폴더(exports/)에 써 두고 file:// 주소를 돌려준다 → 웹이 공유 시트(@capacitor/share)로 넘긴다.
  /// (웹은 먼저 웹 공유 navigator.share 를 쓰고, 그게 없을 때 여기로 온다.)
  /// 큰 파일은 여러 번에 나눠 온다 (append). 이름은 마지막 조각만 써서 폴더 밖으로 못 나가게 한다
  @objc func saveFile(_ call: CAPPluginCall) {
    let name = ((call.getString("name") ?? "1414.txt") as NSString).lastPathComponent.replacingOccurrences(of: ":", with: "_")
    if name.isEmpty || name == "." || name == ".." { call.reject("파일 이름이 이상해요"); return }
    let data = Data((call.getString("data") ?? "").utf8)
    let dir = FileManager.default.temporaryDirectory.appendingPathComponent("exports", isDirectory: true)
    let url = dir.appendingPathComponent(name)
    do {
      try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
      if call.getBool("append") ?? false, FileManager.default.fileExists(atPath: url.path) {
        let h = try FileHandle(forWritingTo: url)
        defer { try? h.close() }
        try h.seekToEnd()
        try h.write(contentsOf: data)
      } else {
        try data.write(to: url, options: .atomic)
      }
      call.resolve(["uri": url.absoluteString])
    } catch { call.reject(error.localizedDescription) }
  }

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
