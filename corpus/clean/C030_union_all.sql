SELECT CustomerID AS Id, LastName AS Name, 'Customer' AS Kind FROM dbo.Customer UNION ALL SELECT EmployeeID, FullName, 'Employee' FROM dbo.Employee;
