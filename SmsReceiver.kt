package com.riduan.smshub

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
import java.util.regex.Pattern

class SmsReceiver : BroadcastReceiver() {
    private val client = OkHttpClient()
    // আপনার ফায়ারবেস রিয়েলটাইম ডাটাবেস URL
    private val dbUrl = "https://payment-verify-ri-default-rtdb.firebaseio.com/transactions"

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == "android.provider.Telephony.SMS_RECEIVED") {
            val bundle = intent.extras
            if (bundle != null) {
                val pdus = bundle.get("pdus") as Array<*>
                for (pdu in pdus) {
                    val sms = SmsMessage.createFromPdu(pdu as ByteArray, bundle.getString("format"))
                    val sender = sms.displayOriginatingAddress ?: ""
                    val message = sms.displayMessageBody ?: ""

                    processMessage(sender, message)
                }
            }
        }
    }

    private fun processMessage(sender: String, message: String) {
        var method = "Unknown"
        val senderLower = sender.lowercase()

        if (senderLower.contains("bkash")) method = "bKash"
        else if (senderLower.contains("nagad")) method = "Nagad"
        else if (senderLower.contains("rocket")) method = "Rocket"
        else return // অন্য মেসেজ ইগনোর করবে

        // Regex দিয়ে Amount এবং TrxID বের করা
        val trxPattern = Pattern.compile("TrxID\\s+([A-Z0-9]+)", Pattern.CASE_INSENSITIVE)
        val amtPattern = Pattern.compile("Tk\\s+([0-9.]+)", Pattern.CASE_INSENSITIVE)
        
        val trxMatcher = trxPattern.matcher(message)
        val amtMatcher = amtPattern.matcher(message)

        if (trxMatcher.find() && amtMatcher.find()) {
            val trxId = trxMatcher.group(1)
            val amount = amtMatcher.group(1).toDouble()
            
            pushToFirebase(trxId, amount, method)
        }
    }

    private fun pushToFirebase(trxId: String, amount: Double, method: String) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val json = JSONObject()
                json.put("amount", amount)
                json.put("method", method)
                json.put("status", "UNCLAIMED") // অন্য ওয়েবসাইট এটি ভেরিফাই করে VERIFIED করবে
                json.put("timestamp", System.currentTimeMillis())

                val body = json.toString().toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url("$dbUrl/$trxId.json") // TrxID কেই কী (Key) হিসেবে ব্যবহার করা হচ্ছে
                    .put(body)
                    .build()

                client.newCall(request).execute()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
