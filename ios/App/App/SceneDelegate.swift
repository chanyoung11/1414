import UIKit
import WebKit
import Capacitor

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }

        window = UIWindow(windowScene: windowScene)
        window?.rootViewController = MainViewController()
        window?.makeKeyAndVisible()

        SceneDelegateProxy.shared.scene(scene, willConnectTo: session, options: connectionOptions)
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        SceneDelegateProxy.shared.scene(scene, openURLContexts: URLContexts)
    }

    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        SceneDelegateProxy.shared.scene(scene, continue: userActivity)
    }
}

/// 앱 안에 둔 플러그인(PrinterPlugin: 인쇄·파일 내보내기·오디오 포커스)은 패키지가 아니라서 Capacitor 가 저절로 찾지 않는다.
/// 전에는 파일만 있고 빌드에도 등록에도 빠져 있어, iOS 에서 인쇄·내보내기·연습 녹음 오디오 포커스가 아무 일도 하지 않았다
class MainViewController: CAPBridgeViewController {
    private var dialogs: KoreanDialogs?   // 웹뷰의 uiDelegate 는 약한 참조라 여기서 붙잡아 둔다

    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(PrinterPlugin())
        // 웹의 confirm()·alert()·prompt() 창을 한국어 단추로 (아래 KoreanDialogs)
        if let wv = webView, let base = wv.uiDelegate {
            let d = KoreanDialogs(base: base, host: self)
            dialogs = d
            wv.uiDelegate = d
        }
    }
}

/// 웹의 confirm()·alert()·prompt() 창. Capacitor 의 기본 창은 단추 글자가 영어("Cancel"/"Ok")로 박혀 있어(지역화도 안 된다)
/// 한국어 앱의 로그아웃·삭제 확인이 영어 단추로 떴다 → 이 셋만 한국어 단추(취소/확인)로 직접 띄운다.
/// 나머지 WKUIDelegate 일(새 창 열기 등)과, Capacitor 가 prompt 로 주고받는 쿠키·HTTP 신호는 원래 처리기로 그대로 넘긴다
final class KoreanDialogs: NSObject, WKUIDelegate {
    private let base: WKUIDelegate   // Capacitor 의 WebViewDelegationHandler
    private weak var host: UIViewController?

    init(base: WKUIDelegate, host: UIViewController) {
        self.base = base
        self.host = host
        super.init()
    }

    // 여기서 만들지 않은 메서드는 원래 처리기가 받는다. 웹뷰는 uiDelegate 를 받을 때 무엇에 답하는지 한 번 물어 둔다
    override func responds(to aSelector: Selector!) -> Bool {
        return super.responds(to: aSelector) || base.responds(to: aSelector)
    }

    override func forwardingTarget(for aSelector: Selector!) -> Any? {
        return base.responds(to: aSelector) ? base : super.forwardingTarget(for: aSelector)
    }

    /// 지금 맨 위 화면 (인쇄·공유 창이 떠 있으면 그 위에). 못 띄우면 웹이 답을 영영 못 받아 멈추므로 곧바로 '취소'로 답한다
    private func top() -> UIViewController? {
        var vc = host
        while let p = vc?.presentedViewController, !p.isBeingDismissed { vc = p }
        return vc
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        guard let vc = top() else { completionHandler(); return }
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "확인", style: .default) { _ in completionHandler() })
        vc.present(a, animated: true)
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard let vc = top() else { completionHandler(false); return }
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "취소", style: .cancel) { _ in completionHandler(false) })
        a.addAction(UIAlertAction(title: "확인", style: .default) { _ in completionHandler(true) })
        vc.present(a, animated: true)
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        // Capacitor 안쪽 신호({"type":"CapacitorCookies.get"} 같은 JSON)는 창 없이 원래 처리기가 답한다
        if let data = prompt.data(using: .utf8),
           let obj = try? JSONSerialization.jsonObject(with: data, options: .fragmentsAllowed) as? [String: Any],
           let type = obj["type"] as? String, type.hasPrefix("Capacitor") {
            base.webView?(webView, runJavaScriptTextInputPanelWithPrompt: prompt, defaultText: defaultText, initiatedByFrame: frame, completionHandler: completionHandler)
            return
        }
        guard let vc = top() else { completionHandler(nil); return }
        let a = UIAlertController(title: nil, message: prompt, preferredStyle: .alert)
        a.addTextField { $0.text = defaultText }
        a.addAction(UIAlertAction(title: "취소", style: .cancel) { _ in completionHandler(nil) })
        a.addAction(UIAlertAction(title: "확인", style: .default) { [weak a] _ in completionHandler(a?.textFields?.first?.text ?? defaultText) })
        vc.present(a, animated: true)
    }
}
