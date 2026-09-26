package com.lets1414.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.provider.Settings;
import android.webkit.MimeTypeMap;
import android.webkit.WebView;

import androidx.activity.result.ActivityResult;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;

/** WebView 안에 그려 둔 인쇄 조판을 안드로이드 인쇄(또는 PDF 저장)로 넘긴다.
 *  웹의 window.print() 는 WebView 에서 아무 일도 하지 않는다. */
@CapacitorPlugin(name = "Printer")
public class PrinterPlugin extends Plugin {

  // 파일 내보내기(콘티 파일·MusicXML). 웹뷰의 <a download> 는 아무 일도 하지 않아서, 웹이 만든 글을
  // 캐시 폴더(exports/)에 써 두고 file:// 주소를 돌려준다 → 웹이 공유 시트(@capacitor/share)로 넘기거나 기기에 저장한다(saveToDevice).
  // 캐시 폴더는 file_paths.xml 의 cache-path 라 FileProvider 로 다른 앱에 건넬 수 있다.
  // 큰 파일은 여러 번에 나눠 온다 (append). 이름은 마지막 조각만 써서 폴더 밖으로 못 나가게 한다
  @PluginMethod
  public void saveFile(final PluginCall call) {
    writeExport(call, call.getString("data", "").getBytes(java.nio.charset.StandardCharsets.UTF_8));
  }

  // 글이 아닌 파일(합주 녹음). 웹뷰에서 바이트를 그대로 못 넘겨 base64 조각으로 온다 → 풀어서 쓴다.
  // saveFile 로 보내면 UTF-8 글로 써져 소리 파일이 깨진다
  @PluginMethod
  public void saveBytes(final PluginCall call) {
    byte[] b;
    try { b = android.util.Base64.decode(call.getString("data", ""), android.util.Base64.DEFAULT); }
    catch (IllegalArgumentException e) { call.reject("파일 조각이 이상해요"); return; }
    writeExport(call, b);
  }

  /** 웹이 준 이름을 exports/ 안의 파일로. 폴더 밖(../)으로는 못 나간다. 이상하면 null */
  private java.io.File exportFile(String raw) {
    String name = new java.io.File(raw == null ? "" : raw).getName().replace(':', '_');
    if (name.isEmpty() || name.equals(".") || name.equals("..")) return null;
    return new java.io.File(new java.io.File(getContext().getCacheDir(), "exports"), name);
  }

  private void writeExport(PluginCall call, byte[] bytes) {
    java.io.File f = exportFile(call.getString("name", "1414.txt"));
    if (f == null) { call.reject("파일 이름이 이상해요"); return; }
    try {
      java.io.File dir = f.getParentFile();
      if (!dir.isDirectory() && !dir.mkdirs()) { call.reject("임시 폴더를 만들지 못했어요"); return; }
      try (java.io.OutputStream os = new java.io.FileOutputStream(f, Boolean.TRUE.equals(call.getBoolean("append", false)))) {
        os.write(bytes);
      }
      JSObject r = new JSObject();
      r.put("uri", Uri.fromFile(f).toString());
      call.resolve(r);
    } catch (Exception e) {
      call.reject(e.getMessage() == null ? "파일을 쓰지 못했어요" : e.getMessage());
    }
  }

  // '기기에 저장' (AND2-06). 공유 시트에는 저장할 곳이 없다 (Quick Share·Drive·Gmail 만 — 올리기에 실패한 까닭인 오프라인에서는
  // Drive·Gmail 도 바로 안 된다). saveFile·saveBytes 로 exports/ 에 써 둔 파일을 저장 위치 고르기(다운로드 등)로 옮긴다.
  // 인터넷 없이 된다. 고르지 않고 닫으면 {saved:false}
  @PluginMethod
  public void saveToDevice(final PluginCall call) {
    java.io.File f = exportFile(call.getString("name"));
    if (f == null || !f.isFile()) { call.reject("저장할 파일을 찾지 못했어요"); return; }
    Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
    i.addCategory(Intent.CATEGORY_OPENABLE);
    i.setType(mimeOf(f.getName()));
    i.putExtra(Intent.EXTRA_TITLE, f.getName());
    try { startActivityForResult(call, i, "savedToDevice"); }
    catch (Exception e) { call.reject("저장 위치를 고르는 창을 열지 못했어요"); }
  }

  // 확장자로 파일 종류를 정한다 — 저장 창(DocumentsUI)은 종류와 이름의 확장자가 다르면 확장자를 하나 더 붙인다 (녹음.m4a.mp4).
  // 모르는 확장자(.musicxml)는 octet-stream 이면 이름을 그대로 둔다
  private static String mimeOf(String name) {
    int dot = name.lastIndexOf('.');
    String ext = dot < 0 ? "" : name.substring(dot + 1).toLowerCase(java.util.Locale.ROOT);
    String m = ext.isEmpty() ? null : MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
    return m == null ? "application/octet-stream" : m;
  }

  @ActivityCallback
  private void savedToDevice(final PluginCall call, ActivityResult result) {
    if (call == null) return;
    final Uri dest = result.getResultCode() == Activity.RESULT_OK && result.getData() != null ? result.getData().getData() : null;
    if (dest == null) {
      JSObject r = new JSObject(); r.put("saved", false); call.resolve(r); getBridge().releaseCall(call); return;
    }
    final java.io.File f = exportFile(call.getString("name"));
    if (f == null) { call.reject("저장할 파일을 찾지 못했어요"); getBridge().releaseCall(call); return; }
    // 큰 녹음도 있으니 옮기기는 뒤에서
    new Thread(() -> {
      try (java.io.InputStream in = new java.io.FileInputStream(f);
           java.io.OutputStream out = getContext().getContentResolver().openOutputStream(dest, "w")) {
        if (out == null) throw new java.io.IOException("저장할 곳을 열지 못했어요");
        byte[] buf = new byte[64 * 1024];
        for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
        JSObject r = new JSObject(); r.put("saved", true); call.resolve(r);
      } catch (Exception e) {
        call.reject(e.getMessage() == null ? "기기에 저장하지 못했어요" : e.getMessage());
      } finally { getBridge().releaseCall(call); }
    }).start();
  }

  // 권한(마이크)을 두 번 거절하면 안드로이드는 다시 묻지 않는다 → 앱 정보 화면을 열어 켜게 한다 (AND2-10)
  @PluginMethod
  public void openAppSettings(final PluginCall call) {
    try {
      Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", getContext().getPackageName(), null));
      getActivity().startActivity(i);
      call.resolve();
    } catch (Exception e) { call.reject("설정을 열지 못했어요"); }
  }

  // 상태바 뒤 띠 = 창 배경. 안드로이드 15 부터 상태바 색 지정이 무시돼서 창 배경을 테마 색으로 칠한다
  @PluginMethod
  public void setWindowBackground(final PluginCall call) {
    final String color = call.getString("color", "#111213");
    getActivity().runOnUiThread(new Runnable() {
      @Override public void run() {
        try {
          getActivity().getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(android.graphics.Color.parseColor(color)));
          call.resolve();
        } catch (Exception e) { call.reject(e.getMessage()); }
      }
    });
  }

  // 웹이 주는 것: name, 그리고 인쇄 조판이면 orient("landscape"|"portrait") · paper("A4"|"Letter") (iOS PrinterPlugin.swift 와 같다).
  // 인쇄 창의 처음 용지·방향을 조판에 맞춘다 (AND2-01) — 안 주면 늘 Letter 세로로 열려 A4 가로 쪽이 위쪽에 작게 찍혔다.
  // 여백은 0 (조판 쪽 = 종이 한 장, 웹은 '여백 없음'으로 찍으라고 안내한다). 인쇄 창에서 바꿀 수 있다.
  // 창이 떠 있는 동안 앱이 얼지 않게 PrintKeepAlive 를 켜 둔다 — 안 그러면 10초쯤 뒤 앱이 얼어, 용지·방향을 바꾸면
  // 'Preparing preview…' 에서 멈추고 앱 JS 까지 응답이 없었다 (AND2-02).
  // 답은 인쇄 창이 닫힐 때(onFinish) 한다 {done:true} (iOS 처럼) — 그때까지 웹이 인쇄 조판(body.nprint)을 남겨 둔다
  // (창에서 옵션을 바꾸면 웹뷰가 지금 화면을 다시 조판한다)
  @PluginMethod
  public void print(final PluginCall call) {
    final String name = call.getString("name", "1414");
    final String orient = call.getString("orient");
    final String paper = call.getString("paper");
    getActivity().runOnUiThread(new Runnable() {
      @Override public void run() {
        try {
          WebView wv = getBridge().getWebView();
          PrintManager pm = (PrintManager) getContext().getSystemService(Context.PRINT_SERVICE);
          if (pm == null) { call.reject("이 기기에서 인쇄를 쓸 수 없어요"); return; }
          final PrintDocumentAdapter inner = wv.createPrintDocumentAdapter(name);
          PrintDocumentAdapter adapter = new PrintDocumentAdapter() {
            private boolean done = false;
            @Override public void onStart() { inner.onStart(); }
            @Override public void onLayout(PrintAttributes oldA, PrintAttributes newA, android.os.CancellationSignal cs, LayoutResultCallback cb, android.os.Bundle extras) {
              inner.onLayout(oldA, newA, cs, cb, extras);
            }
            @Override public void onWrite(android.print.PageRange[] pages, android.os.ParcelFileDescriptor dest, android.os.CancellationSignal cs, WriteResultCallback cb) {
              inner.onWrite(pages, dest, cs, cb);
            }
            @Override public void onFinish() {
              inner.onFinish();
              PrintKeepAlive.stop(getContext());
              if (done) return;
              done = true;
              JSObject r = new JSObject();
              r.put("done", true);
              call.resolve(r);
            }
          };
          PrintAttributes.Builder b = new PrintAttributes.Builder();
          if (orient != null || paper != null) {
            PrintAttributes.MediaSize ms = "Letter".equalsIgnoreCase(paper) ? PrintAttributes.MediaSize.NA_LETTER : PrintAttributes.MediaSize.ISO_A4;
            b.setMediaSize("landscape".equals(orient) ? ms.asLandscape() : ms.asPortrait());
            b.setMinMargins(PrintAttributes.Margins.NO_MARGINS);
          }
          PrintKeepAlive.start(getContext());
          pm.print(name, adapter, b.build());
        } catch (Exception e) {
          PrintKeepAlive.stop(getContext());
          call.reject(e.getMessage() == null ? "인쇄를 열지 못했어요" : e.getMessage());
        }
      }
    });
  }
}
