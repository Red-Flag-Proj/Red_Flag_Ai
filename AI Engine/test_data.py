sample_transactions = [
    {
        "transaction": {
            "id": 1,
            "amount": 50000,
            "createdAt": "2026-05-04T14:20:00",
            "ipCountry": "KR",
            "deviceId": "device_01"
        },
        "context": {
            "avgAmount7d": 70000,
            "knownDeviceIds": ["device_01"],
            "recentTransactions": []
        }
    },
    {
        "transaction": {
            "id": 2,
            "amount": 1500000,
            "createdAt": "2026-05-04T15:10:00",
            "ipCountry": "KR",
            "deviceId": "device_02"
        },
        "context": {
            "avgAmount7d": 300000,
            "knownDeviceIds": ["device_02"],
            "recentTransactions": []
        }
    },
    {
        "transaction": {
            "id": 3,
            "amount": 1200000,
            "createdAt": "2026-05-04T02:30:00",
            "ipCountry": "US",
            "deviceId": "device_03"
        },
        "context": {
            "avgAmount7d": 250000,
            "knownDeviceIds": ["device_03"],
            "recentTransactions": []
        }
    },
    {
        "transaction": {
            "id": 4,
            "amount": 80000,
            "createdAt": "2026-05-04T13:00:00",
            "ipCountry": "JP",
            "deviceId": "device_new_04"
        },
        "context": {
            "avgAmount7d": 60000,
            "knownDeviceIds": ["device_old_04"],
            "recentTransactions": [
                {"createdAt": "2026-05-04T12:59:10"},
                {"createdAt": "2026-05-04T12:59:30"},
                {"createdAt": "2026-05-04T12:59:50"}
            ]
        }
    },
    {
        "transaction": {
            "id": 5,
            "amount": 2000000,
            "createdAt": "2026-05-04T03:10:00",
            "ipCountry": "CN",
            "deviceId": "device_new_05"
        },
        "context": {
            "avgAmount7d": 400000,
            "knownDeviceIds": ["device_old_05"],
            "recentTransactions": [
                {"createdAt": "2026-05-04T03:09:10"},
                {"createdAt": "2026-05-04T03:09:30"},
                {"createdAt": "2026-05-04T03:09:50"}
            ]
        }
    }
]