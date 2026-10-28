SELECT DISTINCT e.EmployeeID, e.FullName FROM dbo.Employee e INNER JOIN dbo.SalesOrderHeader h ON h.SalesPersonID = e.EmployeeID;
