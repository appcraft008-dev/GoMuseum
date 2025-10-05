#!/bin/bash

# 清理 Flutter 应用的本地 Drift 数据库缓存
# 用途：解决本地缓存中存储了旧的识别失败记录的问题

DB_PATH="$HOME/Library/Containers/com.example.gomuseumApp/Data/Documents/gomuseum.db"

echo "GoMuseum - Drift Database Cache Cleaner"
echo "========================================"
echo ""

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database file not found at: $DB_PATH"
    echo "   The app may not have been run yet."
    exit 1
fi

echo "📍 Database location: $DB_PATH"
echo ""

# 显示当前缓存统计
echo "📊 Current cache statistics:"
echo "----------------------------"
total=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM recognition_results;")
unknown=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM recognition_results WHERE artwork_name='Unknown Artwork';")
success=$((total - unknown))

echo "   Total records: $total"
echo "   Successful: $success"
echo "   Failed (Unknown Artwork): $unknown"
echo ""

if [ "$unknown" -eq 0 ] && [ "$total" -eq 0 ]; then
    echo "✅ Cache is already clean!"
    exit 0
fi

# 显示失败记录详情
if [ "$unknown" -gt 0 ]; then
    echo "❌ Failed recognition records:"
    echo "----------------------------"
    sqlite3 -header -column "$DB_PATH" "SELECT
        substr(image_hash, 1, 16) || '...' as hash,
        artwork_name,
        artist,
        confidence,
        datetime(timestamp, 'unixepoch', 'localtime') as time
    FROM recognition_results
    WHERE artwork_name='Unknown Artwork'
    ORDER BY timestamp DESC;"
    echo ""
fi

# 询问用户选择
echo "Select an option:"
echo "  1) Clear ALL cache (all $total records)"
echo "  2) Clear only failed records ($unknown records)"
echo "  3) Cancel"
echo ""
read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        sqlite3 "$DB_PATH" "DELETE FROM recognition_results;"
        echo "✅ All cache cleared successfully!"
        ;;
    2)
        sqlite3 "$DB_PATH" "DELETE FROM recognition_results WHERE artwork_name='Unknown Artwork';"
        echo "✅ Failed records cleared successfully!"
        ;;
    3)
        echo "❌ Operation cancelled."
        exit 0
        ;;
    *)
        echo "❌ Invalid choice."
        exit 1
        ;;
esac

# 显示清理后的统计
echo ""
echo "📊 Cache statistics after cleanup:"
echo "----------------------------"
total_after=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM recognition_results;")
echo "   Remaining records: $total_after"
echo ""
echo "🎉 Done! Please restart the GoMuseum app to see the changes."
