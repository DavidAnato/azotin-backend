from django.urls import path

from app_escrow.views import (
    ContractAcceptView,
    ContractApproveView,
    ContractDetailView,
    ContractDisputeView,
    ContractFundView,
    ContractListCreateView,
    ContractRevisionView,
    ContractStartView,
    ContractSubmitView,
    FedaPayCallbackView,
    FedaPayWebhookView,
    WalletHistoryView,
    WalletView,
    WalletWithdrawView,
)

contract_urlpatterns = [
    path("", ContractListCreateView.as_view(), name="contract-list"),
    path("<int:pk>/", ContractDetailView.as_view(), name="contract-detail"),
    path("<int:pk>/accept/", ContractAcceptView.as_view(), name="contract-accept"),
    path("<int:pk>/fund/", ContractFundView.as_view(), name="contract-fund"),
    path("<int:pk>/start/", ContractStartView.as_view(), name="contract-start"),
    path("<int:pk>/submit/", ContractSubmitView.as_view(), name="contract-submit"),
    path("<int:pk>/approve/", ContractApproveView.as_view(), name="contract-approve"),
    path("<int:pk>/revision/", ContractRevisionView.as_view(), name="contract-revision"),
    path("<int:pk>/dispute/", ContractDisputeView.as_view(), name="contract-dispute"),
]

wallet_urlpatterns = [
    path("", WalletView.as_view(), name="wallet"),
    path("history/", WalletHistoryView.as_view(), name="wallet-history"),
    path("withdraw/", WalletWithdrawView.as_view(), name="wallet-withdraw"),
]

payments_urlpatterns = [
    path("fedapay/webhook/", FedaPayWebhookView.as_view(), name="fedapay-webhook"),
    path("fedapay/callback/", FedaPayCallbackView.as_view(), name="fedapay-callback"),
]
