package com.xueyeguanjia.app;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // App 自带的插件要在 super.onCreate 之前注册
        registerPlugin(FocusTimerPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
