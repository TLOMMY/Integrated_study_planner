package com.xueyeguanjia.app;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.PowerManager;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

/**
 * 番茄钟的原生部分：
 *  · 锁屏 / 通知栏显示倒计时（常驻通知，系统自己走秒，App 在后台也准确）；
 *  · 记录最近一次熄屏、亮屏的时间，供网页层区分"熄屏"和"切到别的应用"。
 */
@CapacitorPlugin(
    name = "FocusTimer",
    permissions = { @Permission(strings = { Manifest.permission.POST_NOTIFICATIONS }, alias = "display") }
)
public class FocusTimerPlugin extends Plugin {

    private static final String CHANNEL = "focus-timer";
    private static final int NOTIFICATION_ID = 880001;

    private long lastScreenOff = 0;
    private long lastScreenOn = 0;
    private BroadcastReceiver screenReceiver;

    @Override
    public void load() {
        screenReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                if (Intent.ACTION_SCREEN_OFF.equals(intent.getAction())) lastScreenOff = System.currentTimeMillis();
                else lastScreenOn = System.currentTimeMillis();
            }
        };
        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_SCREEN_OFF);
        filter.addAction(Intent.ACTION_SCREEN_ON);
        ContextCompat.registerReceiver(getContext(), screenReceiver, filter, ContextCompat.RECEIVER_NOT_EXPORTED);
    }

    @Override
    protected void handleOnDestroy() {
        try {
            getContext().unregisterReceiver(screenReceiver);
        } catch (Exception ignored) {}
    }

    /** { lastScreenOff, lastScreenOn, interactive }：时间为毫秒时间戳，0 表示本次启动后还没发生过。 */
    @PluginMethod
    public void screenState(PluginCall call) {
        PowerManager pm = (PowerManager) getContext().getSystemService(Context.POWER_SERVICE);
        JSObject ret = new JSObject();
        ret.put("lastScreenOff", lastScreenOff);
        ret.put("lastScreenOn", lastScreenOn);
        ret.put("interactive", pm == null || pm.isInteractive());
        call.resolve(ret);
    }

    @Override
    @PluginMethod
    public void checkPermissions(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("display", displayState());
        call.resolve(ret);
    }

    @Override
    @PluginMethod
    public void requestPermissions(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33 || getPermissionState("display") == PermissionState.GRANTED) {
            checkPermissions(call);
            return;
        }
        requestPermissionForAlias("display", call, "permissionResult");
    }

    @PermissionCallback
    private void permissionResult(PluginCall call) {
        checkPermissions(call);
    }

    private String displayState() {
        if (NotificationManagerCompat.from(getContext()).areNotificationsEnabled()) return "granted";
        return Build.VERSION.SDK_INT >= 33 && getPermissionState("display") != PermissionState.GRANTED ? "prompt" : "denied";
    }

    /**
     * 显示 / 更新倒计时通知。
     * { title, text, endAt（进行中：结束时刻的毫秒时间戳）, paused }
     */
    @PluginMethod
    public void show(PluginCall call) {
        Context context = getContext();
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            call.resolve();
            return;
        }
        ensureChannel(context);
        String title = call.getString("title", "专注中");
        String text = call.getString("text", "");
        boolean paused = Boolean.TRUE.equals(call.getBoolean("paused", false));
        Long endValue = call.getLong("endAt");
        long endAt = endValue == null ? 0L : endValue;
        long now = System.currentTimeMillis();

        Intent launch = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
        PendingIntent open = launch == null
            ? null
            : PendingIntent.getActivity(context, 0, launch, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_focus)
            .setContentTitle(title)
            .setContentText(text)
            .setOngoing(!paused)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_STOPWATCH)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setPriority(NotificationCompat.PRIORITY_LOW);
        if (open != null) builder.setContentIntent(open);
        if (!paused && endAt > now) {
            // 系统按 when 倒数走秒；到点后自动收起，不会出现负数
            builder.setShowWhen(true).setWhen(endAt).setUsesChronometer(true).setChronometerCountDown(true);
            builder.setTimeoutAfter(endAt - now + 1000);
        } else {
            builder.setShowWhen(false).setUsesChronometer(false);
        }
        try {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, builder.build());
        } catch (SecurityException ignored) {}
        call.resolve();
    }

    @PluginMethod
    public void hide(PluginCall call) {
        NotificationManagerCompat.from(getContext()).cancel(NOTIFICATION_ID);
        call.resolve();
    }

    private void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null || manager.getNotificationChannel(CHANNEL) != null) return;
        NotificationChannel channel = new NotificationChannel(CHANNEL, "专注计时", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("专注进行中时在通知栏和锁屏显示剩余时间");
        channel.setShowBadge(false);
        channel.setSound(null, null);
        channel.enableVibration(false);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        manager.createNotificationChannel(channel);
    }
}
