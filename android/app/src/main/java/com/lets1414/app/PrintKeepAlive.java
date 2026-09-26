package com.lets1414.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

/**
 * 인쇄 창이 떠 있는 동안 앱 프로세스를 깨워 둔다 (AND2-02).
 *
 * 인쇄 창(PrintActivity)은 다른 앱(인쇄 스풀러)의 화면이라, 그 뒤에 가린 우리 앱은 '캐시된 앱'이 되고 안드로이드 14+ 는
 * 약 10초 뒤 프로세스를 얼린다(cached apps freezer). 그런데 인쇄 창은 용지·방향을 바꿀 때마다 우리 앱의 인쇄 어댑터에
 * 다시 조판·쓰기를 부탁한다(단방향 바인더 호출) — 얼어 있으면 그 부탁이 풀릴 때까지 쌓이기만 해서 'Preparing preview…' 가
 * 끝나지 않았다 (앱 JS 도 얼어 응답이 없었다). 짧은 포그라운드 서비스(shortService, 최대 약 3분)가 도는 동안은 얼리지 않는다.
 * 인쇄 창이 닫히면(onFinish) 멈춘다. 알림은 조용한 '인쇄 창이 열려 있어요' 하나.
 */
public class PrintKeepAlive extends Service {
  private static final String CHANNEL = "print";
  private static final int NOTI_ID = 1414;

  static void start(Context ctx) {
    try { ContextCompat.startForegroundService(ctx, new Intent(ctx, PrintKeepAlive.class)); }
    catch (Exception ignored) {}   // 못 켜면 전처럼 (옵션을 바로 안 바꾸면 인쇄는 된다)
  }

  static void stop(Context ctx) {
    try { ctx.stopService(new Intent(ctx, PrintKeepAlive.class)); } catch (Exception ignored) {}
  }

  @Override public int onStartCommand(Intent intent, int flags, int startId) {
    NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
    if (Build.VERSION.SDK_INT >= 26 && nm != null && nm.getNotificationChannel(CHANNEL) == null) {
      NotificationChannel ch = new NotificationChannel(CHANNEL, "인쇄", NotificationManager.IMPORTANCE_LOW);
      ch.setShowBadge(false);
      nm.createNotificationChannel(ch);
    }
    Notification n = new NotificationCompat.Builder(this, CHANNEL)
      .setSmallIcon(R.drawable.ic_stat_noti)
      .setContentTitle("인쇄 창이 열려 있어요")
      .setContentText("인쇄하거나 닫으면 사라져요")
      .setOngoing(true)
      .setSilent(true)
      .setPriority(NotificationCompat.PRIORITY_LOW)
      .build();
    try {
      if (Build.VERSION.SDK_INT >= 34) startForeground(NOTI_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SHORT_SERVICE);
      else startForeground(NOTI_ID, n);
    } catch (Exception e) {
      stopSelf();
    }
    return START_NOT_STICKY;
  }

  // shortService 는 약 3분이면 시스템이 끝내라고 한다 — 바로 멈춘다 (안 멈추면 앱이 죽는다)
  @Override public void onTimeout(int startId) { stopSelf(); }

  @Override public IBinder onBind(Intent intent) { return null; }
}
