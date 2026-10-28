SELECT OrderID, TotalDue, (SELECT MAX(OrderDate) FROM dbo.SalesOrderHeader) AS LatestOrderDate FROM dbo.SalesOrderHeader WHERE Status = 1;
