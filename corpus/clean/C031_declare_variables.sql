DECLARE @from DATETIME = '2024-01-01'; DECLARE @to DATETIME = '2025-01-01'; SELECT OrderID, TotalDue FROM dbo.SalesOrderHeader WHERE OrderDate >= @from AND OrderDate < @to;
