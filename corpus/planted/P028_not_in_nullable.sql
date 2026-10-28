SELECT EmployeeID, FullName FROM dbo.Employee WHERE EmployeeID NOT IN (SELECT SalesPersonID FROM dbo.SalesOrderHeader WHERE OrderDate >= '2024-01-01');
