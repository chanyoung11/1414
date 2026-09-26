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

  /// 웹이 주는 것: name, 그리고 인쇄 조판이면 orient("landscape"|"portrait") · paper("A4"|"Letter") · pageW/pageH(쪽 크기, CSS px).
  /// 웹의 @page{size:A4 landscape} 는 viewPrintFormatter 가 따르지 않는다 → 방향과 쪽 비율은 여기서 맞춘다 (C1).
  /// 종이(paper)는 프린터 기본·인쇄 창에서 고른 것을 그대로 둔다 — UIPrintPaper.bestPaper 는 같은 종이가 없으면 더 큰
  /// Legal·A3 를 고를 수 있다. 어느 종이든 쪽 비율 칸(PagePrintRenderer)에 한 장씩 담긴다
  @objc func print(_ call: CAPPluginCall) {
    DispatchQueue.main.async {
      guard let webView = self.bridge?.webView else {
        call.reject("화면을 찾지 못했어요"); return
      }
      // 배경색(하이라이트·검은 송폼 띠·흰 글씨 딱지)을 지우지 않는다 (C2). 웹 조판은 print-color-adjust:exact 로 이미 청한다 —
      // 이 설정(기본 꺼짐)은 그 CSS 가 없는 것까지 배경을 남기는 뒷받침이다 (iOS 16.4 아래는 CSS 만)
      if #available(iOS 16.4, *) { webView.configuration.preferences.shouldPrintBackgrounds = true }
      let info = UIPrintInfo(dictionary: nil)
      info.outputType = .general
      info.jobName = call.getString("name") ?? "1414"
      // 인쇄 창의 기본 방향 = 웹에서 고른 방향 (인쇄 창에서 바꿀 수도 있다). 안 주면(재구성 악보) 전처럼 세로
      info.orientation = call.getString("orient") == "landscape" ? .landscape : .portrait
      let controller = UIPrintInteractionController.shared
      controller.printInfo = info
      let formatter = webView.viewPrintFormatter()
      let pageW = call.getDouble("pageW") ?? 0, pageH = call.getDouble("pageH") ?? 0
      if pageW > 0, pageH > 0 {
        // 쪽 한 장 = 종이 한 장 (PagePrintRenderer)
        let renderer = PagePrintRenderer()
        renderer.pageRatio = CGFloat(pageH / pageW)
        renderer.addPrintFormatter(formatter, startingAtPageAt: 0)
        controller.printFormatter = nil
        controller.printPageRenderer = renderer
      } else {
        controller.printPageRenderer = nil
        controller.printFormatter = formatter
      }
      controller.present(animated: true) { (_, completed, error) in
        if let error = error { call.reject(error.localizedDescription) }
        else { call.resolve(["completed": completed]) }
      }
    }
  }
}

/// 인쇄 조판은 쪽(.ppage, A4 가로면 1123×794px) 하나가 종이 한 장이다. 그런데 WebKit 은 인쇄 가능 영역의 가로:세로 비율로
/// 문서를 잘라 장을 나눈다 (장 높이 = 문서 폭 × 영역 높이/폭, 내림). 프린터·PDF 의 인쇄 가능 영역은 사방 여백을 뺀 것이라
/// 가로로 놓으면 A4 보다 납작하다(806×559pt → 1123px 폭에 779px) → 794px 쪽이 한 장에 안 들어가 쪽마다 끝이 빈 장으로 넘어간다.
/// 그래서 인쇄 가능 영역 안에 쪽 비율 칸을 가운데 두고 그 칸에만 찍게 한다 (C1). 세로도 같은 이유로 맞춘다
final class PagePrintRenderer: UIPrintPageRenderer {
  /// 쪽 세로/가로 (0 이면 인쇄 가능 영역 그대로)
  var pageRatio: CGFloat = 0

  override var printableRect: CGRect {
    let r = super.printableRect
    guard pageRatio > 0, r.width > 0, r.height > 0 else { return r }
    // 1.5% 더 길게 — 딱 맞으면 WebKit 의 내림과 쪽 크기의 소수점(793.7px) 때문에 쪽 끝 1px 이 다음 장으로 넘어갈 수 있다 (쪽 밑이 조금 빈다)
    let ratio = pageRatio * 1.015
    var w = r.width, h = w * ratio
    if h > r.height { h = r.height; w = h / ratio }
    return CGRect(x: r.midX - w / 2, y: r.midY - h / 2, width: w, height: h)
  }
}
