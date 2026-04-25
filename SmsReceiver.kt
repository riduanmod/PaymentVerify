package com.riduan.smsforwarder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.SmsMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class SmsReceiver : BroadcastReceiver() {
    private val client = OkHttpClient()
    private val apiUrl = "http://YOUR_SERVER_IP:8000/api/sms-webhook" // Replace with your backend URL
    private val apiKey = "Secure_API_Key_For_Android_App_123!"

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == "android.provider.Telephony.SMS_RECEIVED") {
            val bundle = intent.extras
            if (bundle != null) {
                val pdus = bundle.get("pdus") as Array<*>
                for (pdu in pdus) {
                    val sms = SmsMessage.createFromPdu(pdu as ByteArray, bundle.getString("format"))
                    val sender = sms.displayOriginatingAddress ?: ""
                    val message = sms.displayMessageBody ?: ""

                    // Filter for BD MFS
                    if (sender.contains("bKash", true) || sender.contains("Nagad", true) || sender.contains("Rocket", true)) {
                        sendToBackend(sender, message)
                    }
                }
            }
        }
    }

    private fun sendToBackend(sender: String, message: String) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val json = JSONObject()
                json.put("sender", sender)
                json.put("message", message)
                json.put("timestamp", System.currentTimeMillis() / 1000)

                val body = json.toString().toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(apiUrl)
                    .addHeader("X-API-Key", apiKey)
                    .post(body)
                    .build()

                client.newCall(request).execute()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
