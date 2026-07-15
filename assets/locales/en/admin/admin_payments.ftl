# Admin manual payment review and billing moderation texts.

kb-admin-pay-approve = ✅ Approve { $amount }
kb-admin-pay-custom = ✏️ Custom Amount
kb-admin-pay-reject = ❌ Reject

admin-pay-review-card-title-new = 📥 <b>New invoice payment request</b>
admin-pay-review-card-title-topup = 🔄 <b>Additional payment request</b>
admin-pay-review-card-already-paid = Already confirmed: { $amount }
admin-pay-review-card-needed = Remaining to be paid: { $amount }
admin-pay-user-profile-link = 👤 User Profile
admin-pay-wrong-chat = This button only works in the private payment review group.
admin-pay-invoice-not-found = Request not found or no longer available.
admin-pay-already-processed = This request has already been processed.
admin-pay-custom-amount-prompt =
    Enter the confirmed amount for invoice { $invoice_id }.

    Expected amount: { $expected_amount }
admin-pay-enter-rejection-reason = Enter the rejection reason for the user.
admin-pay-custom-amount-invalid = Invalid amount. Enter a value like `25` or `25.5`.
admin-pay-approve-done = Payment confirmed
admin-pay-reject-done = Payment rejected
admin-pay-review-processing = ⏳ Processing: { $admin }
admin-pay-review-processed-by = 👤 Processed by admin: { $admin }
admin-pay-review-result-title = ✅ <b>Review completed</b>
admin-pay-review-result-subscription = Subscription activated until { $new_end }.
admin-pay-review-result-error = Result code: { $error }
admin-pay-review-rejected =
    ❌ <b>Request rejected</b>

    Invoice: { $invoice_id }
    Reason: { $reason }
