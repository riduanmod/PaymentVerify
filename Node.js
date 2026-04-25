const axios = require('axios');

async function verifyPaymentFromHub(userSubmittedTrxId, userSubmittedAmount) {
    const dbUrl = `https://payment-verify-ri-default-rtdb.firebaseio.com/transactions/${userSubmittedTrxId}.json`;

    try {
        // 1. ফায়ারবেস থেকে ট্রানজেকশন ডাটা আনা
        const response = await axios.get(dbUrl);
        const txData = response.data;

        // 2. ডাটা না থাকলে বা আগেই ব্যবহৃত হয়ে থাকলে রিজেক্ট করা
        if (!txData) return { success: false, message: "Transaction not found." };
        if (txData.status === "VERIFIED") return { success: false, message: "Transaction already used!" };

        // 3. অ্যামাউন্ট মিলিয়ে দেখা
        if (parseFloat(txData.amount) === parseFloat(userSubmittedAmount)) {
            
            // 4. সব ঠিক থাকলে ফায়ারবেসে স্ট্যাটাস VERIFIED করে দেওয়া
            await axios.patch(dbUrl, { status: "VERIFIED" });
            
            return { success: true, message: "Payment verified successfully!" };
        } else {
            return { success: false, message: "Amount mismatch." };
        }
    } catch (error) {
        console.error("Verification Error:", error);
        return { success: false, message: "Internal server error." };
    }
}
